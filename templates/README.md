# Templates

Shared LaTeX venue templates, one folder per venue. Bundled so far (pulled
from the PaperOrchestra repo, MIT-licensed style files):

- `cvpr2025/` — `.sty`, `.bst`, `preamble.tex`, `template.tex`, `guidelines.md`
- `iclr2025/` — `.sty`, `.bst`, `preamble.tex`/`math_commands.tex`, `template.tex`, `guidelines.md`

## Adding another venue (NeurIPS, IEEEtran, ACL, Nature, etc.)

Either:
- Drop the venue's official `.cls`/`.sty`/`.bst` files into a new
  `templates/<venue>/` folder yourself, or
- Ask Claude to fetch the specific venue's current public style files (name
  the exact venue/year) and it will create the folder here.

Don't let a paper drift onto a generic `article` layout — every paper folder
under `papers/` should copy its working `.tex`/`.sty` set from here rather than
inventing one.
