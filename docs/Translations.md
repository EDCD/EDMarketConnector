# Translations in Elite Dangerous Market Connector

The application supports translations for most of the text you will see in its UI.

Translations are handled on [Crowdin](https://crowdin.com/), specifically in [this project](https://crowdin.com/project/edmarketconnector).

If you'd like to contribute then please sign in or make an account there.

---

## Adding A New Phrase

### Setting it up in the code

#### Call `tr.tl(...)`
If you add any new strings that appear in the application UI, e.g. new configuration options, then you should specify them as:

	tr.tl('Text that appears in UI')

In order to do this, you must add the following import: 

`from l10n import translations as tr`

`tr.tl()` is a function that then handles the translation, using its single argument, plus the configured language, to look up the appropriate text. 

If you need to specify something in the text that shouldn't be translated then use the form:

	tr.tl('Some text with a {WORD} not translated').format(WORD='word')
This way 'word' will always be used literally.

#### Add a LANG comment

Sometimes our translators may need some additional information about what a
translation is used for. You can add that information automatically by using
`# LANG: your message here` **on the line directly above your usage, or at the
end of the line in your usage**. If both comments exist, the one on the
current line is preferred over the one above

```py
from l10n import translations as tr
# LANG: this says stuff.
tr.tl('stuff')
```

#### Edit `L10n/en.template` to add the phrase

##### Hint: It is strongly recommended to use the `find_localized_strings.py` script to help automate this process!
	/* <use of this phrase> [<file it was first added in>] */
	"<text as it appears in the code>" = "<English version of the text>";
e.g.

	/* Successfully authenticated with the Frontier website. [EDMarketConnector.py] */
	"Authentication successful" = "Authentication successful";
which matches with:

	self.status['text'] = tr.tl('Authentication successful')    # Successfully authenticated with the Frontier website

and

	/* Help text in settings. [prefs.py] */
	"Tip: You can disable a plugin by{CR}adding '{EXT}' to its folder name" = "Tip: You can disable a plugin by{CR}adding '{EXT}' to its folder name";
which matches with:

	nb.Label(plugsframe, text=tr.tl("Tip: You can disable a plugin by{CR}adding '{EXT}' to its folder name").format(EXT='.disabled')).grid(     # Help text in settings
`{CR}` is handled in `l10n.py`, translating to a Unicode `\n`.  See the code in`l10n.py` for any other such special substitutions.

You can even use other translations within a given string, e.g.:

	tr.tl("One or more of your enabled plugins do not yet have support for Python 3.x. Please see the list on the '{PLUGINS}' tab of '{FILE}' > '{SETTINGS}'. You should check if there is an updated version available, else alert the developer that they need to update the code for Python 3.x.\r\n\r\nYou can disable a plugin by renaming its folder to have '{DISABLED}' on the end of the name.".format(PLUGINS=tr.tl('Plugins'), FILE=tr.tl('File'), SETTINGS=tr.tl('Settings'), DISABLED='.disabled'))
	/* Popup body: Warning about plugins without Python 3.x support [EDMarketConnector.py] */
"One or more of your enabled plugins do not yet have support for Python 3.x. Please see the list on the '{PLUGINS}' tab of '{FILE}' > '{SETTINGS}'. You should check if there is an updated version available, else alert the developer that they need to update the code for Python 3.x.\r\n\r\nYou can disable a plugin by renaming its folder to have '{DISABLED}' on the end of the name." = "One or more of your enabled plugins do not yet have support for Python 3.x. Please see the list on the '{PLUGINS}' tab of '{FILE}' > '{SETTINGS}'. You should check if there is an updated version available, else alert the developer that they need to update the code for Python 3.x.\r\n\r\nYou can disable a plugin by renaming its folder to have '{DISABLED}' on the end of the name.";

## Contributing Translations

**We do not accept GitHub Pull Requests for any changes to translations, except for "silly" languages.** Pull Requests on GitHub will be closed and not included.

The exception to this is funny languages like "UwU", "Klingon", or other not-real languages if people want to have fun.

Users requesting to join the translation team can submit a request on the Crowdin page, or contact Rixxan to request to be added to the translation page.

1. Periodically, the en.template file will be synced with Crowdin.
   1. If Crowdin is significantly out of date compared to the template, please open a Bug Report or contact Rixxan.
2. Translations can be submitted directly to Crowdin.

All project admins will get a notification of the new upload.  Now you wait for translators to work on the new/changed phrases.

---

## Updating Translations In The Code

Once you have new/changed translations on Crowdin, you'll want to update the code to use them.

1. All approved translations can be exported as a ZIP file from [this page](https://crowdin.com/project/edmarketconnector/translations.)
2. Users should "build and download" the zip file, then replace the new file in the project.
3. Alternatively, individual translation files can be downloaded from the Dashboard page.
4. Changed files should be submitted to Git

---

## Adding a New Language

If you feel able to contribute a full translation for an additional language then please [open an issue](https://github.com/EDCD/EDMarketConnector/issues/new?assignees=&labels=Translations&template=new-translation-language.md&title=%5BTranslations%5D+New+language+-+)
to request the language be added. If approved, you'll be invited to join the Crowdin page. Then, follow these directions:

1. Request the new language on Crowdin.
2. Provide relevant translations. 
3. Remember that until there are translations all strings will default to the default version (Generally, English).

Guidelines
---
There are a number of things about the phrases on Crowdin that might seem confusing at first.

1. The 'Language name' phrase should have 'English' changed to the word for the target language in
  that language.  This should *not* be the word for 'English' in the target language.  e.g., for
  the German translation this is "Deutsch" *not* "Englisch".

2. Any text of the form `{THING}`, i.e., curly braces around a word, should be left as is in the
  translation.  These words are *not* translated, but have the fixed text substituted in by the
  application.
  
    As part of this, `{CR}` becomes a newline, i.e., text continues on the next line.

    An example of this is the phrase `About {APP}` which should have 'About' translated, but keep
    the '{APP}' intact as it would be replaced with the text 'E:D Market Connector' to make the
    entire phrase "About E:D Market Connector" in the original English.

3. In addition to the previous point, there's at least one instance of the string `%H:%M:%S` which
  should be left as-is, not translated.  The comment on the relevant phrase calls this out, so
  in general, pay attention to those comments.

4. Any phrase that matches an in-game name should be left as it shows in-game.  If the
  game has a translation for your language, then do use the in-game translation for this.
  Examples include:
    1. The name of any rank category, e.g., "Combat", "CQC", "Powerplay".
    2. Combat Ranks, e.g., "Harmless".
    3. Trade Ranks.
    4. Exploration Ranks.
    5. CQC Ranks.
    6. Ranks with the Superpowers (Empire and Federation).
 
    If we're on the ball, we'll have finalized these phrases when we add the language.

Testing Changes
---
Whether it be for a new language, an additional phrase in an existing translation, or changing
a translation, the only way to test the changes is to obtain the corresponding `<lang>.strings` file
and copy it into the `L10n\` folder in your install of EDMC.

If you are comfortable [running from source](https://github.com/EDCD/EDMarketConnector#running-from-source), 
that is probably easiest. Just replace the appropriate file.

If you want to test with the currently installed application, then you'll need to find its
install folder (default `C:\Program Files x(86)\EDMarketConnector`) and replace the appropriate
file in the `L10n` sub-folder.

If your changes have been committed to GitHub, then you should be able to find the updated strings
file in the [L10n folder of the develop branch](https://github.com/EDCD/EDMarketConnector/tree/develop/L10n).  Click
into the appropriate file, then:

1. Right-click the `Raw` button top-right of the file contents.
2. `Save Link As...` from the context menu.

NB: This is correct for Firefox; the menu entry and method might vary in other browsers. 
If all else fails, click into `Raw`, then select all the text and paste it into a file.

You'll need to restart the application to be sure it's entirely picked up the new translations.

If your changes are not yet in the `develop` branch, then ask a maintainer to create a new, temporary,
branch with your changes so you can access them from there.
