# German language pack for ProcessWire

German (de_DE) language pack for [ProcessWire](http://processwire.com). 
Uses formal language ("Sie").

The repository will (try to) be up to date with the most recent **stable** version of ProcessWire. For use with a **dev** version use the dev branch.

Language packs for (some) older versions of ProcessWire are available on the [releases page](https://github.com/jmartsch/pw-lang-de/releases) of this repository.

## Installation

To install a language pack, you must have the ProcessWire Language Support module installed. This is included with ProcessWire, so all you have to do is click to Modules > Language > Language Support > install.

Once you have Language Support installed, you can install this language pack by going to Setup > Languages > Add New Language. Enter a title and name for the language and save.

Next, you can install the files for the language pack. If your system supports ZIP uploads, you can simply drag the ZIP file for the language pack into the files field. If your system doesn't support ZIP uploads, then you'll want to unzip the language pack and drag the JSON files (as a group, or individually) into the files field. Save.

Now you can test out the new language by editing our profile and selecting the new language.

Menu items are translated after you log out and log in again.

Big thanks to yellowled and nico for their initial work.

## How to help updating the language pack (draft, not ready yet)
Pull requests are welcome. Let's try to work together, to get fast updates of the german language pack when a new stable version is published.

* Admin > Setup > Languages > Add New
* Save
* Press button: 'Find Files to Translate'
* Select all files in the box 'Translatable files in /wire/'
* Select files in the box 'Translatable files in /site/' which you want to add to your custom language pack
* Press 'Submit'
* Start translating
* Download zip or csv file by pressing the related button at the bottom of the page where translatable files are listed.

Look for abandoned and empty phrases.
abandoned are not needed any more and can safely be removed
empty phrases are new additions, which need to be translated