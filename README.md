# AI Office Builder

Turn scattered files into an AI office: a manager, specialist agents, client or
class workspaces, and a second-brain Library. Your code lives separately in `~/Code`.

1. Download **ai-office-builder.skill** from [Releases](https://github.com/michaelgiebelhausen/ai-office-builder/releases/latest).
2. In Claude, open **Customize → Skills**, click **+ → Create skill → Upload a skill**, and select the file.
   If the picker requires `.zip`, rename the downloaded file to
   `ai-office-builder.zip`—it is already a ZIP archive. Enable the uploaded skill.
   See [Claude's installation guide](https://support.claude.com/en/articles/12512180-use-skills-in-claude).
3. Start a local-file-capable Claude Cowork session, grant access only to the
   folders you want organized, and say **“build my AI office.”** A normal web chat
   cannot rearrange files on your computer. Claude Code users can instead extract
   the archive into `~/.claude/skills/` and use the same phrase.

Allow **60–90 minutes**. Claude interviews you, scans without moving anything,
proposes a floor plan, then asks you to approve each move bundle. You can stop
and resume from the log. Each bundle has a saved preview and an undo file. Changed files invalidate the preview; destination contents are verified after moving. Session snapshots preserve your choices when resuming. Supported local links are checked, and uncertain app dependencies need your review. Occupied destinations are
never overwritten. Exact duplicates move to a review folder. Renaming is optional.

```text
OneDrive/Cowork/
  00_Inbox/           To sort, duplicates, migration log and undo files
  01_Library/         raw_human, raw_AI, and one wiki per agent
  10–19_Agents/       Your AI team, each with its own job description
  20–29_Clients/      Clients, employers or a student side hustle
  30–39_Personal/     Professionals only; student personal bots use the 10s
~/Code/              GitHub projects, outside OneDrive
```

Windows works with Python or built-in PowerShell. On Mac, Python 3 may need to be
installed; do not assume it is present. Moves between different drives are
refused so the tool never silently switches to copying and deleting.

MIT licensed. Test instructions: [DEVELOPING.md](DEVELOPING.md).
