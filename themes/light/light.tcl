package require Tk 8.6

namespace eval ttk::theme::light {

    variable version 1.0
    package provide ttk::theme::light $version
    variable colors
    array set colors {
        -fg         "black"
        -bg         "#dcdad5"
        -disabledfg "#999999"
        -selectfg   "white"
        -selectbg   "#9e9a91"
        -highlight  "blue"
    }
    variable font TkDefaultFont
    variable font_u [font create {*}[font configure TkDefaultFont] -underline 1]

    ttk::style theme create light -parent clam -settings {
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
            -font $font \
            -borderwidth 1 \
            -relief flat

        tk_setPalette background $colors(-bg) \
            foreground $colors(-fg) \
            highlightColor $colors(-selectbg) \
            selectBackground $colors(-selectbg) \
            selectForeground $colors(-fg) \
            activeBackground $colors(-selectbg) \
            activeForeground $colors(-fg)

        ttk::style map . -foreground [list disabled $colors(-disabledfg)]

        option add *Font $font
        option add *Menu.selectcolor $colors(-fg)

        ttk::style configure TLabel -padding 1

        ttk::style configure Link.TLabel -foreground $colors(-highlight)
        ttk::style map Link.TLabel \
            -font [list active $font_u] \
            -foreground [list disabled $colors(-disabledfg)] \
            -cursor [list disabled arrow]

        ttk::style configure TLabelframe -relief groove

        ttk::style configure TEntry -padding 2

        ttk::style configure TButton -padding {8 4 8 4} -width -10 -anchor center -relief groove
        ttk::style map TButton \
            -background [list pressed $colors(-selectbg)] \
            -foreground [list pressed $colors(-selectfg)]

        ttk::style configure Toolbutton -padding {8 4 8 4} -width -10 -anchor center

        ttk::style configure TMenubutton -padding {8 4 4 4} -relief groove -arrowcolor $colors(-fg)
        ttk::style map TMenubutton \
            -background [list active $colors(-selectbg)] \
            -foreground [list active $colors(-selectfg)] \
            -arrowcolor [list active $colors(-selectfg)]
        ttk::style configure Menubar.TMenubutton -padding 2 -relief flat -arrowsize 0

        ttk::style configure TCheckbutton -padding 4 -indicatormargin 4

        ttk::style configure ToggleButton -padding {8 4 8 4} -width -10 -anchor center

        ttk::style configure TRadiobutton -padding 4 -indicatormargin 4

        ttk::style configure TSpinbox -padding 2 -arrowsize 10

        ttk::style configure TCombobox -padding 2

        ttk::style configure TNotebook -padding 2
        ttk::style configure TNotebook.Tab -padding 2

        ttk::style configure Treeview.Item -padding {2 0 0 0}
        ttk::style map Treeview \
            -background [list selected $colors(-selectbg)] \
            -foreground [list selected $colors(-selectfg)]

        ttk::style configure TScrollbar -troughcolor $colors(-selectbg)

        ttk::style configure TScale -troughcolor $colors(-selectbg)

        ttk::style configure TProgressbar -troughcolor $colors(-selectbg)
    }
}
