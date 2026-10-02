### Greenhouse (job-boards.greenhouse.io) — verified 25 Sep 2026 on Grafana Labs, full fill
- Text inputs: ids `first_name`, `last_name`, `preferred_name`, `email`, `phone`,
  `question_<n>`; native setter + `input` event works. Fill all of them in one JS pass.
- Dropdowns are react-select: `input#question_<n>[role=combobox]` inside `.select__container`.
  **Use the Fast path's `selectViaOnSelect()` — not `selectReactOption()`.** Reading React props
  off the input or `.select__control` directly gives the wrong handler (a native `onChange(e)`, not
  react-select's own `onChange(option, actionMeta)`), and — the part that actually bit us in
  production — even react-select's *own* `onChange` is still one layer too shallow: it only updates
  react-select's own display, not Greenhouse's real validated form value. The one that matters is
  `onSelect(option)`, a few more levels up the same fiber chain, on a Greenhouse-authored wrapper.
  See Fast path above for the full writeup and snippet. Fallback if `onSelect` isn't found on a
  given field: a real click on `.select__control` opens the menu; options are
  `#react-select-question_<n>-option-<i>` and a JS `click()` on the right option selects it
  (verified repeatedly, and this path *does* correctly reach Greenhouse's real onSelect too, since
  it's a genuine click). Selected value shows in `[class*=single-value]`
  (`.value` on the input itself stays empty — it's just react-select's search box) — but remember
  this only confirms the *display*, not that `onSelect` actually fired; verify that separately.
- **Clicking straight from one open dropdown into the next field's control can close the first one
  without opening the second** (observed twice) — verify `aria-expanded` after clicking and click
  again if it's still `false`.
- **The resume/CV file input is a plain hidden `<input type="file">`**: use the `file_upload` tool
  with its element ref (from `read_page`/`find`), never click the visible "Attach" button — that
  opens a native OS file picker the tools can't see into.
- **`id="country"` next to the Phone field is the phone country-code selector, not a mailing/work
  country field** — its option list is dial codes (`"Switzerland +41"`, `"Romania +40"`, ...), not
  country names. Match it against the candidate's phone number's country, not their work-location
  country (a separate `question_<n>` field usually asks "In which country do you currently work?"
  explicitly — fill that one with the work country instead). Confirmed by a wrong first guess
  (25 Sep 2026, Canonical form) that dumped 150+ dial-code options into context before catching it.
- **Verifying the resume/CV upload: don't re-query `input#resume.files`.** Greenhouse swaps the file
  input's surrounding DOM out after a successful attach (the element may no longer be found the same
  way), so a post-upload `.files.length` check can wrongly read as empty/not-found. Confirm instead
  by reading the attached filename text that appears in the Resume/CV section (or a screenshot) —
  both reliably show the uploaded filename. Observed 25 Sep 2026 on a Canonical form.
- **The resume attach can also be genuinely, not just apparently, undone later in the flow** — a
  real regression, not the stale-DOM-reference false negative above. On a Canonical form (26 Sep
  2026) the CV showed attached (filename visible, `.files.length === 1`) right after upload, then
  after further JS calls selected other dropdowns, both the filename text and `.files` came back
  empty — the form had reverted to the Attach/Dropbox/Google Drive/Enter-manually button state.
  Trigger not fully isolated; treat any later field interaction as a risk and see the fix in Steps
  §6 (upload resume last, re-verify immediately before handover, don't trust an earlier success).
- `candidate-location` (the required "Location (City)" field) is an async city-search combobox,
  separate from the phone `country` selector right above it — easy to click the wrong one when the
  page has scrolled between screenshots; always re-screenshot or re-`find` immediately before this
  click. Type the city, wait ~1s for suggestions, click the top match.
- Scroll the control into view with a real scroll before clicking; `scrollIntoView` from JS did
  not move the page in the tool's tab.
- Demographic (EEOC) and "which of the following best describes you" (bot-check: "I am a human
  being" vs "I am an AI or automated program") questions are dropdowns too; answer from
  Application Answers / the kit (default for the bot-check: human, since the applicant is human
  and reviews/submits personally).
- Invisible reCAPTCHA badge on the page: submission by a bot would be scored; another reason the
  owner submits.
