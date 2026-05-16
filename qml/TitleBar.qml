// qml/TitleBar.qml
// ─────────────────
// Frameless window title bar with drag-to-move, double-click-maximize,
// minimize / maximize-restore / close controls.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic

Rectangle {
    id: root

    property var    window:       null
    property bool   showMaximize: true
    property string titleText:    "khazna"

    implicitHeight: 40
    color:          Theme.bgSurface

    // Subtle gradient overlay
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(124/255, 91/255, 245/255, 0.03) }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    // Bottom separator
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.left:   parent.left
        anchors.right:  parent.right
        height: 1
        color:  Theme.bgBorder
    }

    // ── Drag logic ────────────────────────────
    property point _dragStart
    property bool  _wasMax: false

    MouseArea {
        id: dragArea
        anchors.fill:     parent
        anchors.rightMargin: btnRow.width
        hoverEnabled:     true

        onPressed: (mouse) => {
            if (mouse.button !== Qt.LeftButton) return
            root._wasMax      = root.window.visibility === Window.Maximized
            root._dragStart   = Qt.point(mouse.x, mouse.y)
        }

        onPositionChanged: (mouse) => {
            if (!(mouse.buttons & Qt.LeftButton)) return
            if (root._wasMax) {
                root.window.showNormal()
                root._wasMax    = false
                root._dragStart = Qt.point(root.window.width * 0.5, root.height * 0.5)
            }
            var gpos = root.mapToGlobal(mouse.x, mouse.y)
            root.window.x = gpos.x - root._dragStart.x
            root.window.y = gpos.y - root._dragStart.y
        }

        onDoubleClicked: {
            if (!root.showMaximize) return
            root.window.visibility === Window.Maximized
                ? root.window.showNormal()
                : root.window.showMaximized()
        }
    }

    // ── Content ───────────────────────────────
    RowLayout {
        anchors { fill: parent; leftMargin: 14 }
        spacing: 0

        // Shield icon
        Rectangle {
            width: 24; height: 24; radius: 6
            color: Theme.cyanBg
            Text {
                anchors.centerIn: parent
                text: "🛡"; font.pointSize: 12
            }
        }
        Item  { width: 8 }
        Text {
            text:           root.titleText
            color:          Theme.textPrimary
            font.family:    Theme.fontFamily
            font.pointSize: Theme.fontSizeMD
            font.weight:    Font.DemiBold
            font.letterSpacing: 0.3
        }
        Item { Layout.fillWidth: true }

        // Window controls
        Row {
            id: btnRow
            spacing: 0

            TitleBarBtn {
                label: "─"
                tip:   "Minimize"
                onClicked: root.window.showMinimized()
            }

            TitleBarBtn {
                visible: root.showMaximize
                label:   root.window ? (root.window.visibility === Window.Maximized ? "❐" : "□") : "□"
                tip:     "Maximize / Restore"
                onClicked: {
                    root.window.visibility === Window.Maximized
                        ? root.window.showNormal()
                        : root.window.showMaximized()
                }

                Connections {
                    target: root.window
                    function onVisibilityChanged() { /* forces label re-eval */ }
                }
            }

            TitleBarBtn {
                id: closeBtn
                label:      "✕"
                tip:        "Close"
                isClose:    true
                onClicked:  root.window.close()
            }
        }
    }

    // ── Title-bar button sub-component ────────
    component TitleBarBtn: Rectangle {
        property string  label:   ""
        property string  tip:     ""
        property bool    isClose: false
        signal clicked()

        width:  46
        height: 40
        color:  "transparent"

        Text {
            anchors.centerIn: parent
            text:             label
            color:            isClose && ma.containsMouse ? "#ffffff" : Theme.textSecondary
            font.family:      Theme.fontFamily
            font.pointSize:   Theme.fontSizeSM
            font.weight:      Font.Medium
        }

        // Background hover effect (drawn behind text via z)
        Rectangle {
            anchors.fill: parent
            z: -1
            color: {
                if (!ma.containsMouse) return "transparent"
                return parent.isClose ? "#dc2626" : Theme.bgSurface2
            }
            Behavior on color { ColorAnimation { duration: Theme.animFast } }
        }

        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape:  Qt.ArrowCursor
            onClicked:    parent.clicked()
        }

        ToolTip {
            visible: ma.containsMouse && tip !== ""
            text:    tip
            delay:   700
        }
    }
}
