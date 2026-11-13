# Sample output

Output of `sh examples/run-example.sh` — the checker run over
the whole `examples/` folder (2 CSS files, 22 declarations,
7 problems in 1 file):

```
examples/clean.css: OK — 12 declaration(s), none use !important
FAIL examples/messy.css:3: property 'color' uses '!important'
FAIL examples/messy.css:8: property 'margin' uses '!important'
FAIL examples/messy.css:13: property 'Padding' uses '!important'
FAIL examples/messy.css:19: property 'width' uses '!important'
FAIL examples/messy.css:24: property 'color' uses '!important'
FAIL examples/messy.css:25: property 'background' uses '!important'
FAIL examples/messy.css:29: property '--brand' uses '!important'
Checked 2 CSS file(s) (22 declaration(s)), 7 problem(s) in 1 file(s).
```

The seven uses are `color` in `.card`, `margin` in `.btn`
(written as `! important`, with a space), `Padding` in
`.title` (written as `!IMPORTANT`), `width` in `.sidebar`
inside the media query, `color` and `background` together
in `.alert`, and the custom property `--brand` in `:root`.
The clean stylesheet mentions `!important` in a comment
and inside a `content: "!important"` string — neither is a
declaration using it, so the file passes.
