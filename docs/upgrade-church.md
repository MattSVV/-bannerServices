# Upgrading the church's OpenLP to 3.1.8

Portadas needs **OpenLP 3.1.8**. This guide upgrades an older OpenLP safely, with a way back. Do it on a weekday, not on a service morning, and on the same computer that runs the services.

Facts were checked against the OpenLP 3.1.8 source (`gitlab.com/openlp/openlp`, tag `3.1.8`), cited as `file:line` inside that repository. Anything not checked is marked **(unverified)**. Download OpenLP only from <https://openlp.org>; this guide does not point to any other site.

## What OpenLP does by itself

Knowing this explains the steps below:

- On the first start after an upgrade OpenLP offers to copy the data folder to a sibling folder named `<data folder>-<date>-<time>` (`openlp/core/app.py:217-250`). **Say Yes**, but do not rely on it alone: it only happens after the new version has started.
- If the stored settings version differs, OpenLP also writes a settings backup `<data folder>/<date> <time>.conf` and upgrades the settings in place (`app.py:337-394`).
- OpenLP does **not** support going back: when it finds settings from a *newer* version, it moves the whole data folder aside, clears the settings and starts fresh (`app.py:344-394`). Rolling back therefore means restoring your own backup, not just reinstalling the old version.
- A settings file exported from a newer OpenLP is refused on import (`openlp/core/ui/mainwindow.py:902-909`).
- Songs and other databases are upgraded by OpenLP's own migration code on first use (`openlp/core/db/upgrades.py`). Whether every possible old database version migrates cleanly to 3.1.8 is **(unverified)**; this is why a full backup comes first.
- The OpenLP 3.1.8 release notes are not in the source tree we read (`CHANGELOG.rst` stops at 3.1.3), so read them at openlp.org before installing **(unverified)**.

## 0. Before anything: who and when

- Pick one person to do the upgrade and keep the old installer and the backups until two normal services have run on 3.1.8.
- Make sure nobody else has OpenLP open on that computer. Close OpenLP.

## 1. Check the current version

1. Open OpenLP, then **Help > About OpenLP** (the About dialog, `mainwindow.py:292`). Write down the version.
2. Note how OpenLP was installed (installer from openlp.org, a Linux package, a portable copy). Note the operating system and whether it is 32 or 64 bit **(whether 3.1.8 supports an old system is unverified: check openlp.org)**.
3. If the version is already 3.1.8, skip to [install.md](install.md).

## 2. Back up (do not skip)

### 2.1 Export the settings from the old OpenLP

**File > Export > Settings**, save the `.conf` file somewhere safe (`mainwindow.py:317,964-980`). This file is what you can import back into the old version if you roll back. It keeps your settings but not your songs or media.

### 2.2 Copy the data folder

Close OpenLP, then copy the whole data folder to a safe place (an external drive or another computer). Use a copy, not a move.

| System | Data folder | Source |
|--------|-------------|--------|
| Windows | `%APPDATA%\openlp\data` | `openlp/core/common/applocation.py:137-140` |
| macOS | `~/Library/Application Support/openlp/Data` | `applocation.py:145-149` |
| Linux | `~/.local/share/openlp` | `applocation.py:145,162-164` |

If the church set a custom data folder (Settings > Configure OpenLP > Advanced), that folder is the one to copy (`applocation.py:75-90`). A portable OpenLP keeps everything in its `Data` and `Other` folders next to the program (`app.py:447-470,533-536`): copy the whole portable folder.

The data folder holds the songs database, themes, images, media, presentations and service files saved in the default place. Service files (`.osz`) you saved elsewhere are not inside it: copy those too.

### 2.3 Settings outside the data folder

OpenLP's settings are normally kept by Qt in the system (registry on Windows, a preferences file on macOS and Linux) **(unverified: this is Qt's default behaviour; the OpenLP code only chooses an INI file for portable mode, `app.py:447-461`)**. The exported `.conf` from 2.1 is your copy of these.

### 2.4 Check the backup

- The data folder copy opens and has similar size to the original.
- The `.conf` file is not empty.
- Ideally, restore the copy on another computer with the old OpenLP and see that songs appear **(recommended, not required)**.

## 3. Install 3.1.8

1. Download the 3.1.8 installer for your system from <https://openlp.org> and keep the file.
2. Install it. If the old version was installed with an installer, installing over it is the usual way **(unverified for your specific old version: check openlp.org for notes about upgrading from it)**. A portable copy is upgraded by using the new portable download next to (not over) the old folder.
3. Start OpenLP.
4. When asked *"OpenLP has been upgraded, do you want to create a backup of the old data folder?"* answer **Yes** (`app.py:229-250`). Note where the backup was written. A *Settings Backup* message may also appear (`app.py:372-376`).
5. Check **Help > About OpenLP** shows 3.1.8.

## 4. Check that services still work

Before installing Portadas, test on the real data:

- Songs: search for a few songs, open one, add it to the service.
- Open the last saved service file, check songs, Bible verses, images and media.
- Check themes and the output screen (projector or second monitor), and the presentations tool if the church uses it.
- Confirm backup copies are still untouched.

If something is wrong, do not continue: use section 6.

## 5. Install Portadas

Follow [install.md](install.md). Install Portadas only after step 4 passes, so that a problem can be blamed on one change at a time.

## 6. Roll back

Do this if 3.1.8 does not work for the church and you need the old version for Sunday.

1. Close OpenLP 3.1.8.
2. Rename the 3.1.8 data folder to `<name>-3.1.8` (do not delete it).
3. Copy your backup from 2.2 to the original data folder location, so it has the original name.
4. Reinstall the old OpenLP with the installer you kept.
5. Start the old OpenLP. If settings look wrong, import the `.conf` from 2.1 with **File > Import > Settings** (`mainwindow.py:853-960`). OpenLP warns that this changes your configuration, and it closes itself afterwards (`mainwindow.py:960-962`); start it again.
6. Check songs and the last service as in section 4.

Do not start the old OpenLP on the 3.1.8 data folder: it may treat it as foreign or damage it (the downgrade protection in `app.py:344-394` only exists in versions that contain it **(unverified for the old version)**).

## Checklist

- [ ] Old version noted
- [ ] Settings exported (`.conf`)
- [ ] Data folder copied and checked
- [ ] Service files saved elsewhere copied
- [ ] 3.1.8 installed, data backup offered by OpenLP accepted
- [ ] Songs, last service, themes and output tested
- [ ] Portadas installed and enabled ([install.md](install.md))
- [ ] Old installer and backups kept until two services have run
