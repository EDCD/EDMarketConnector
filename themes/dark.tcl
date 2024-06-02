package require Tk 8.6

namespace eval ttk::theme::dark {

    variable version 1.0
    package provide ttk::theme::dark $version
    variable colors
    array set colors {
        -fg         "#ff8000"
        -bg         "grey4"
        -disabledfg "#aa5500"
        -disabledbg "grey"
        -selectfg   "grey4"
        -selectbg   "#ff8000"
        -highlight  "white"
    }

    ttk::style theme create dark -parent clam -settings {
        ttk::style configure . \
            -background $colors(-bg) \
            -foreground $colors(-fg) \
            -troughcolor $colors(-bg) \
            -focuscolor $colors(-selectbg) \
            -selectbackground $colors(-selectbg) \
            -selectforeground $colors(-selectfg) \
            -insertwidth 1 \
            -insertcolor $colors(-fg) \
            -fieldbackground $colors(-bg) \
            -font {TkDefaultFont 10} \
            -borderwidth 1 \
            -relief flat

        ttk::style map . -foreground [list disabled $colors(-disabledfg)]

        tk_setPalette background [ttk::style lookup . -background] \
            foreground [ttk::style lookup . -foreground] \
            highlightColor [ttk::style lookup . -focuscolor] \
            selectBackground [ttk::style lookup . -selectbackground] \
            selectForeground [ttk::style lookup . -selectforeground] \
            activeBackground [ttk::style lookup . -selectbackground] \
            activeForeground [ttk::style lookup . -selectforeground]

        option add *font [ttk::style lookup . -font]

        ttk::style configure Link.TLabel -foreground $colors(-highlight)

        ttk::style configure TSeparator -background $colors(-fg)

        ttk::style configure TButton -padding {8 4 8 4} -width -10 -anchor center

        ttk::style configure Toolbutton -padding {8 4 8 4} -width -10 -anchor center

        ttk::style configure TMenubutton -padding {8 4 4 4}

        ttk::style configure TOptionMenu -padding {8 4 4 4}

        ttk::style configure TCheckbutton -padding 4

        ttk::style configure ToggleButton -padding {8 4 8 4} -width -10 -anchor center

        ttk::style configure TRadiobutton -padding 4

        ttk::style map TCombobox -selectbackground [list \
            {!focus} $colors(-selectbg) \
            {readonly hover} $colors(-selectbg) \
            {readonly focus} $colors(-selectbg) \
        ]

        ttk::style map TCombobox -selectforeground [list \
            {!focus} $colors(-selectfg) \
            {readonly hover} $colors(-selectfg) \
            {readonly focus} $colors(-selectfg) \
        ]

        ttk::style configure TNotebook -padding 2

        ttk::style configure Treeview -background $colors(-bg)
        ttk::style configure Treeview.Item -padding {2 0 0 0}

        ttk::style map Treeview \
            -background [list selected $colors(-selectbg)] \
            -foreground [list selected $colors(-selectfg)]
    }
}
