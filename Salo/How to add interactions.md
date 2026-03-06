# Make character talk
Main function to make actor talk is `actor_speak`
To reduce boilerplate, there are some helper functions present too like `actor_speak_default`, etc.
But feel free to use whatever one fits your vision more.

# Choose what character says
To determine what character says, you manipulate with the first argument of `actor_speak`, the `file`.

There are several modifiers to any voice lines:
1) character language
2) is character muffled
3) random index

These modifiers represent the actual file system location in this way:
1) character language expects file to be in the folder with pre-defined suffix such as `_eng` for english language
2) muffled voice line expects file name to have prefix `m_`
3) random index expects file name to have numeric suffix as `_1`. Index of random voice line is selected randomly due to `gamedata/configs/plugins/varefined.ltx`

All `Voiced Actor` owned voice lines belong to `gamedata/sounds/characters_voice` and must follow this template:
`gamedata/sounds/characters_voice/<category><language_suffix>/<subcategory>/<muffle><file_name>_<index>.ogg`.

For example, `gamedata/sounds/characters_voice/player_eng/death/m_death_1.ogg`, means:
1) character should speak in english
2) character should have a helmet on (muffled)
3) character should say one of the death lines, and the line is randomly selected from the pool of lines with the same name but different index.

To select a random voice line, you are expected to use `random_voice_line` function which puts all parameters into the template above

To reduce boilerplate here, there are helper functions like `commands_with_lang_muffle`, I highly recommend using them to make code self-documenting and obvious

To select a voice line from several different subcategories, you should use `choose_random_category` function and call it with required subcategories.

## Adding new interaction
Follow these steps to add a new interaction:

### 1. Create the voice line folder#
Create a folder for your voice lines in `gamedata/sounds/characters_voice` following the template `gamedata/sounds/characters_voice/<category><language_suffix>/<subcategory>` for all languages

**Example:** For a "death" interaction in the player category: 
- `gamedata/sounds/characters_voice/player/death/`
- `gamedata/sounds/characters_voice/player_eng/death/`

### 2. Create the description file
Create a `.description` file in folder with no language suffix (russian language) explaining what the interaction does and when it triggers

Run `generate_sound_descriptions.py` to copy that `.description` file to all other language folders 

**Example:** Content of `gamedata/sounds/characters_voice/player/death/`
- When character dies

### 3. Register in configuration
Add it to the `gamedata/configs/plugins/varefined.ltx`
   - Do it manually by adding new entry to all `lines` sections
   - Or Run `scripts/sync_ltx_lines.py` to automatically add new entry to all `lines` sections

**Example:** Content of `varefined.ltx`:
```ini
[lines_rus]
death = 7

[lines_eng]
death = 7
```

### 4. (OPTIONAL) Add voice line files
Add voice lines to the folder if you have them
   - Run `scripts/batch_armorfx.py` to automatically generate muffled versions of your voice lines
   - Run `scripts/fix_filenames.py` to automatically rename your voice lines to fit the template and add indices to them

**Example:** Folder `gamedata/sounds/characters_voice/player_eng/death/` contains:
- `death_1.ogg`
- `m_death_1.ogg`

### 5. Implement the code trigger
Add code in AGDD_voiced_actor.script to trigger your interaction.

For new categories add and modify this block to the one you are creating:
```lua
local VOICE_CATEGORY_MUTANTS = "greetings"

function mutants_with_lang_muffle(subcategory)
    return random_voice_line_and_subcategory_same(VOICE_CATEGORY_MUTANTS, lang, muffle, subcategory)
end
```

If you are looking for dynamic sub-category, you may want to explore function `dialog_with_unique_npc` where it dynamically determines sub-category based on dynamic story_id of an npc character is talking to.

### 6. Update the documentation
Run `scripts/update_readme.py` to update the [Readme.md](Readme.md#implemented-reactions) with new interaction automatically