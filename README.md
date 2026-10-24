    # SigmaOS-GTK

    GTK build patches & theming glue

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/linuxmint/gtk

    ## Design principles applied
    - **Single Source of Truth**
- **Plan Before Act**
- **Fail-Fast**
- **Defensive Programming**
- **KISS**
- **DRY**
- **Deterministic Testing**

    ## Usage
    Verbs: `patches, theme-bridge, deps, wrapper-plan`

    ```
    $ sigma-gtk patches series --patches-dir ./patches
0001-fix-headerbar.patch  -p1  [ok]
0002-gdk-glitch.patch     -p1  [MISSING]
$ sigma-gtk theme-bridge colors.css
@define-color theme_selected_bg_color #5294e2;
$ sigma-gtk deps build-deps.txt
cairo glib gdk-pixbuf pango gtk mpv celluloid
$ sigma-gtk wrapper-plan /usr/bin/celluloid --env GTK_THEME=Mint-Y-Dark
#!/bin/sh
exec "/usr/bin/celluloid" "$@"

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
