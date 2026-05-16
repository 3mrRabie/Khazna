// qml/AutoLockBanner.qml
// ───────────────────────
// Slides in from the top when the vault auto-locks due to inactivity.

import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    width:   380; height: 52
    radius:  Theme.radiusMD
    color:   Qt.rgba(124/255,106/255,247/255, 0.18)
    border.color: Theme.accent
    opacity: 0; visible: opacity > 0
    y: -60

    function show() {
        slideIn.start()
        hideTimer.start()
    }

    SequentialAnimation {
        id: slideIn
        ParallelAnimation {
            NumberAnimation { target: root; property: "opacity"; to: 1; duration: Theme.animNormal }
            NumberAnimation { target: root; property: "y"; to: 0; duration: Theme.animNormal; easing.type: Easing.OutCubic }
        }
    }

    Timer {
        id: hideTimer; interval: 4000
        onTriggered: slideOut.start()
    }

    SequentialAnimation {
        id: slideOut
        ParallelAnimation {
            NumberAnimation { target: root; property: "opacity"; to: 0; duration: Theme.animNormal }
            NumberAnimation { target: root; property: "y"; to: -60; duration: Theme.animNormal; easing.type: Easing.InCubic }
        }
    }

    RowLayout {
        anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
        Text { text: "🔒"; font.pointSize: Theme.fontSizeLG }
        Text {
            text:  "Vault locked due to inactivity"
            color: Theme.textPrimary; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeMD
            Layout.fillWidth: true
        }
        Text {
            text: "✕"; color: Theme.textMuted; font.pointSize: Theme.fontSizeSM
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: slideOut.start() }
        }
    }
}
