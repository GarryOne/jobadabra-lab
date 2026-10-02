### Ashby (jobs.ashbyhq.com/<board>/<id>/application) — verified 25 Sep 2026 on DeepL, no fiber trick needed
- The listing/board API (`api.ashbyhq.com/posting-api/job-board/<slug>`) does **not** expose
  application questions — only posting content. The real form only exists on the live
  `/application` page. Fine for filling live; it just means the kit can't pre-draft Ashby answers
  from an API the way it can for Greenhouse, only from likely-question guesses.
- Plain `<input>`/`<textarea>` with native `<label for>` — `el.labels[0].textContent` gives the
  real question text directly, no DOM archaeology needed. Native setter + `input` event fills them.
- Selection questions are **native checkboxes and radios**, not a custom widget — a plain `.click()`
  works, verified (`checkbox.checked` flips and persists). No react-select, no fiber walk required
  despite the page being React — Ashby renders real native form controls.
- System fields: `#_systemfield_name`, `#_systemfield_email`, resume via `input[type=file]`
  (`#_systemfield_resume`), a phone field, and one `[role=combobox]` text input for
  location/company autocomplete (type + wait + pick, same pattern as Greenhouse's `candidate-location`).
- Overall: **simpler to fill than Greenhouse** once you're on the live page.
