# Language

Generated from `language.jsonl` by the learning pipeline. Do not edit by hand.

## Owner

- Write each deliverable in the language its audience reads, and reply in the language the owner writes in. `lang-match-audience`

## Translation

- Check a translation by blind back-translation of a sample: a fresh helper translates it back without the source, then meaning and facts are compared. An earlier Spanish edition passed this way with zero fact drift. `lang-back-translation`
- Build the glossary before translating: key terms, names that stay untranslated, register. Translators and reviewers both work from it, so terms stay the same across files. `lang-glossary-first`
- Check parity by script: the same number of segments, every placeholder present, and numbers and dates identical in value and formatted for the locale. `lang-parity-script`
- In apps with several languages, keep string tables with identical keys and check parity by script on every change, so no screen falls back to the wrong language. `lang-key-parity`
- All language editions read facts from the same facts file, so a correction in one edition reaches every edition. `lang-shared-facts`
- Translate for a native reader, not word for word: idiom, examples and tone adapt; facts do not. The owner's bar is native quality in both languages. `lang-transcreate`
- A fresh reviewer reads the target text once without the source, for naturalness, then once against it, for fidelity. `lang-two-reads`
- Check translated interface strings for overflow by screenshot at phone width; a translated label that breaks a button is a defect. `lang-ui-overflow`
- Do not translate personal names, place names or product names unless the glossary lists a translation. `lang-names`
