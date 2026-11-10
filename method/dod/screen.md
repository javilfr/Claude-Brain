# Definition of done: Screen

Read before reporting a user interface screen done.

- [ ] Were screenshots captured at phone and desktop widths, light and dark, for every state the spec lists (empty, loading, error, long text)?
- [ ] Are the screenshots newer than the last edit to the screen, and were they looked at?
- [ ] Does it use the design tokens, with no hard-coded colours or spacing?
- [ ] Does it pass an automated accessibility audit, with body text contrast of at least 4.5:1 and touch targets of at least 44 points?
- [ ] Do long text, large text and other UI languages fit without breaking the layout?
- [ ] Does motion respect reduce-motion, with no layout shift on load?
- [ ] Does it avoid every pattern on the brief's list of defaults to avoid, or justify each exception?
- [ ] Are screenshots stored outside git history unless the project chose otherwise?
