### Lever (jobs.lever.co/<board>/<id>/apply) — verified 25 Sep 2026 on Palantir, not a React app at all
- Confirmed `!Object.keys(el).find(k=>k.startsWith('__react'))` — Lever's form has zero React
  involvement. Plain `.value` assignment + `input`/`change` events works on every text field, no
  special technique needed anywhere.
- Named fields, not id'd: use `input[name="org"]` etc., not `#org` — `name="name"`, `name="email"`,
  `name="phone"`, `name="org"` (current company), `name="urls[LinkedIn]"` / `urls[GitHub]` /
  `urls[Portfolio]`.
- `#location-input` is a Google-Places-style autocomplete with a paired hidden
  `#selected-location`; typing into it didn't surface a `.suggestions` list the way tested — needs
  another look before relying on it; a plain typed value may or may not satisfy the paired hidden
  field on its own.
- Checkboxes (e.g. language/skill tags as `cards[<uuid>][field<n>]`) are plain native checkboxes,
  `.click()` works, verified.
- Resume: `#resume-upload-input`, a plain file input — same `file_upload` tool approach as Greenhouse.
