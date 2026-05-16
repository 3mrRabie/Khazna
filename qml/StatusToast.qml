// qml/StatusToast.qml
// ────────────────────
// Transient bottom notification pill that auto-dismisses after 4 seconds.

import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    width:   Math.max(320, msgRow.implicitWidth + 40)
    height:  46
    radius:  Theme.radiusLG
    color:   _bgColor
    border.color: _borderColor
    border.width: 1
    opacity: 0
    visible: opacity > 0

    property color _bgColor:     Theme.bgSurface2
    property color _textColor:   Theme.textPrimary
    property color _borderColor: Theme.bgBorder
    property string _icon: ""

    function show(text, colour) {
        msgText.text = text
        _textColor   = colour || Theme.textPrimary

        if      (colour === Theme.success) { _bgColor = Theme.successBg; _borderColor = Theme.successBorder; _icon = "✓" }
        else if (colour === Theme.danger)  { _bgColor = Theme.dangerBg;  _borderColor = Theme.dangerBorder;  _icon = "✗" }
        else if (colour === Theme.warning) { _bgColor = Theme.warningBg; _borderColor = Theme.warningBorder; _icon = "⚠" }
        else                               { _bgColor = Theme.bgSurface2; _borderColor = Theme.bgBorder;     _icon = "ℹ" }

        showAnim.restart()
        hideTimer.restart()
    }

    ParallelAnimation {
        id: showAnim
        NumberAnimation { target: root; property: "opacity"; to: 1; duration: Theme.animNormal; easing.type: Easing.OutCubic }
        NumberAnimation { target: root; property: "y"; from: root.y + 12; to: root.y; duration: Theme.animNormal; easing.type: Easing.OutCubic }
    }

    Timer {
        id: hideTimer
        interval: 4000
        onTriggered: hideAnim.start()
    }

    NumberAnimation {
        id: hideAnim
        target: root; property: "opacity"; to: 0; duration: Theme.animNormal; easing.type: Easing.InCubic
    }

    RowLayout {
        id: msgRow
        anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
        spacing: 8

        // Status icon
        Rectangle {
            width: 22; height: 22; radius: 11
            color: root._textColor
            visible: root._icon !== ""
            Text {
                anchors.centerIn: parent
                text: root._icon
                color: Theme.textInverse
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeXS
                font.weight: Font.Bold
            }
        }

        Text {
            id: msgText
            color:          root._textColor
            font.family:    Theme.fontFamily
            font.pointSize: Theme.fontSizeSM
            font.weight:    Font.Medium
            Layout.fillWidth: true
            elide: Text.ElideRight
        }
        Text {
            text: "✕"; color: Theme.textMuted; font.pointSize: Theme.fontSizeSM
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: hideAnim.start() }
        }
    }
}
