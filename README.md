# shiraberu
A simple desktop app for dictionary lookups (with OCR functionality) that supports JMdict and EPWING dictionary files

<img src="https://raw.githubusercontent.com/mhtchan/shiraberu/master/images/example_1.png" width="400" height="400">

# Installation
### Dependencies
1. Run `poetry install` to install dependencies (see https://python-poetry.org/docs/#installation for poetry installation)
2. Run `poetry run python main.py`

Alternatively, install the required depdencies listed in `pyproject.toml` manually.

### Dictioanary files
shiraberu only supports dictionary files that have been processed by the Yomichan Import tool (see https://foosoft.net/projects/yomichan-import/ for installation and usage). For example

* JMdict (freely available, see http://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project)

* Proprietary EPWING dictionaries (大辞林, 大辞泉 etc...)

If done correctly, these files should be in `zip` format, which can be imported through the config window.

# Usage

### Wildcards
The lookup functionality accepts the wildcard characters `%` (zero or more characters) and `_` (exactly one character)

For example, `電％` will match `電` and also entries such as `電気`, `電車` and `電子回路`.

### Optical Character Recognition
Images that are pasted into the lookup text box will be translated to text (courtesy of the manga_ocr package). For example, simply copy a portion of the screen (ctrl+win+s on Windows) and paste into the lookup text box.

# Licensing
* This application uses the PyQt library, which is released under the GPL v3. Hence, the code in this repository is also released under the same license (https://github.com/mhtchan/shiraberu/blob/main/LICENSE)
* The files in the `fonts` directory are licensed under the SIL Open Font License.
