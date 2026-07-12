# /b/-shit

This thing is basically an MD5 list that updates dynamically depending on whether I'm awake and spending my miserable time on stupid shit like browsing 4chan and downloading pictures, then hashing them into a list. It's done kinda automatically, kinda semi-automatically.

## Post-script initialization

If you don't have it yet, you'll need to install [ViolentMonkey](https://violentmonkey.github.io) or [Tampermonkey](https://www.tampermonkey.net).

I personally use ViolentMonkey on Firefox and Tampermonkey on Chromium.

Then you'll need the 4chan-X userscript, which you can download here: [4chan-X](https://www.4chan-x.net/builds/4chan-X.user.js).

## Script initialization

To get this working after installing the extension, click on the ViolentMonkey/Tampermonkey icon and go to the script to edit it.

If you're on ViolentMonkey, there's an "Allow editing" checkbox at the top of the screen — check it. Warning: any changes you make will get wiped whenever 4chan-X updates, so you'll have to redo this occasionally.

### 1. Add the `@connect` permission

Find the `==UserScript==` header block:

```
// ==UserScript==
// @name         4chan X
// @version      1.14.24.1
// @minGMVer     1.14
// @minFFVer     26
// @namespace    4chan-X
// @description  4chan X is a script that adds various features to anonymous imageboards.
// @license      MIT; https://github.com/ccd0/4chan-x/blob/master/LICENSE
// @include      http://boards.4chan.org/*
// @include      https://boards.4chan.org/*
```

Somewhere inside that block (before `// ==/UserScript==`), add:

```
// @connect      raw.githubusercontent.com
```

### 2. Append the sync function

Scroll to the very end of the document (Ctrl+End, or Ctrl+Fn+End depending on your keyboard), right after:

```
return Main;
}).call(this);
Main.init();
})();
```

Paste in the contents of [`at_the_end.js`](at_the_end.js) so the end of the file looks like this:

```
return Main;
}).call(this);
Main.init();
})();
(function syncSntlMD5Directly() {
  'use strict';
  if (typeof GM_xmlhttpRequest === 'undefined' || typeof GM_getValue === 'undefined' || typeof GM_setValue === 'undefined') {
    console.error('[SNTL] Missing required GM_ functions.');
    return;
  }
```

That's it — should be running cleanly after that.

## My plans for this thing

I'll try my best to keep it working, but I have a life and I'm not a great programmer, so no promises.
