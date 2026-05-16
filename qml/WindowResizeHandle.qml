// qml/WindowResizeHandle.qml
// ──────────────────────────
// Invisible drag strips along all edges and corners of the frameless window.
// CODE-12 FIX: Added all 8 resize directions.
// Previously only bottom, right, and bottom-right were implemented.

import QtQuick

Item {
    id: root
    property var window: null
    anchors.fill: parent

    readonly property int margin: 6

    // ── Bottom edge ───────────────────────────
    MouseArea {
        anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
        anchors.leftMargin:  root.margin
        anchors.rightMargin: root.margin
        height: root.margin
        cursorShape: Qt.SizeVerCursor
        property int _startY: 0
        property int _startH: 0
        onPressed:  (m) => { _startY = m.y; _startH = root.window.height }
        onPositionChanged: (m) => {
            if (pressed) root.window.height = Math.max(640, _startH + (m.y - _startY))
        }
    }

    // ── Top edge ──────────────────────────────
    MouseArea {
        anchors { top: parent.top; left: parent.left; right: parent.right }
        anchors.leftMargin:  root.margin
        anchors.rightMargin: root.margin
        height: root.margin
        cursorShape: Qt.SizeVerCursor
        property real _startGY: 0
        property int  _startH:  0
        property int  _startWY: 0
        onPressed: (m) => {
            var gp = mapToGlobal(m.x, m.y)
            _startGY = gp.y
            _startH  = root.window.height
            _startWY = root.window.y
        }
        onPositionChanged: (m) => {
            if (!pressed) return
            var gp = mapToGlobal(m.x, m.y)
            var delta = gp.y - _startGY
            var newH = Math.max(640, _startH - delta)
            root.window.y      = _startWY + (_startH - newH)
            root.window.height = newH
        }
    }

    // ── Right edge ────────────────────────────
    MouseArea {
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        anchors.topMargin:    root.margin
        anchors.bottomMargin: root.margin
        width: root.margin
        cursorShape: Qt.SizeHorCursor
        property int _startX: 0
        property int _startW: 0
        onPressed:  (m) => { _startX = m.x; _startW = root.window.width }
        onPositionChanged: (m) => {
            if (pressed) root.window.width = Math.max(960, _startW + (m.x - _startX))
        }
    }

    // ── Left edge ─────────────────────────────
    MouseArea {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        anchors.topMargin:    root.margin
        anchors.bottomMargin: root.margin
        width: root.margin
        cursorShape: Qt.SizeHorCursor
        property real _startGX: 0
        property int  _startW:  0
        property int  _startWX: 0
        onPressed: (m) => {
            var gp = mapToGlobal(m.x, m.y)
            _startGX = gp.x
            _startW  = root.window.width
            _startWX = root.window.x
        }
        onPositionChanged: (m) => {
            if (!pressed) return
            var gp = mapToGlobal(m.x, m.y)
            var delta = gp.x - _startGX
            var newW = Math.max(960, _startW - delta)
            root.window.x     = _startWX + (_startW - newW)
            root.window.width = newW
        }
    }

    // ── Bottom-right corner ───────────────────
    MouseArea {
        anchors { bottom: parent.bottom; right: parent.right }
        width: root.margin * 2; height: root.margin * 2
        cursorShape: Qt.SizeFDiagCursor
        property int _sx: 0; property int _sy: 0
        property int _sw: 0; property int _sh: 0
        onPressed: (m) => { _sx = m.x; _sy = m.y; _sw = root.window.width; _sh = root.window.height }
        onPositionChanged: (m) => {
            if (pressed) {
                root.window.width  = Math.max(960, _sw + (m.x - _sx))
                root.window.height = Math.max(640, _sh + (m.y - _sy))
            }
        }
    }

    // ── Bottom-left corner ────────────────────
    MouseArea {
        anchors { bottom: parent.bottom; left: parent.left }
        width: root.margin * 2; height: root.margin * 2
        cursorShape: Qt.SizeBDiagCursor
        property real _startGX: 0
        property int  _startW:  0
        property int  _startWX: 0
        property int  _startSY: 0
        property int  _startH:  0
        onPressed: (m) => {
            var gp = mapToGlobal(m.x, m.y)
            _startGX = gp.x
            _startW  = root.window.width
            _startWX = root.window.x
            _startSY = m.y
            _startH  = root.window.height
        }
        onPositionChanged: (m) => {
            if (!pressed) return
            var gp = mapToGlobal(m.x, m.y)
            var deltaX = gp.x - _startGX
            var newW = Math.max(960, _startW - deltaX)
            root.window.x     = _startWX + (_startW - newW)
            root.window.width = newW
            root.window.height = Math.max(640, _startH + (m.y - _startSY))
        }
    }

    // ── Top-right corner ──────────────────────
    MouseArea {
        anchors { top: parent.top; right: parent.right }
        width: root.margin * 2; height: root.margin * 2
        cursorShape: Qt.SizeBDiagCursor
        property int  _startSX: 0
        property int  _startW:  0
        property real _startGY: 0
        property int  _startH:  0
        property int  _startWY: 0
        onPressed: (m) => {
            _startSX = m.x
            _startW  = root.window.width
            var gp = mapToGlobal(m.x, m.y)
            _startGY = gp.y
            _startH  = root.window.height
            _startWY = root.window.y
        }
        onPositionChanged: (m) => {
            if (!pressed) return
            root.window.width = Math.max(960, _startW + (m.x - _startSX))
            var gp = mapToGlobal(m.x, m.y)
            var delta = gp.y - _startGY
            var newH = Math.max(640, _startH - delta)
            root.window.y      = _startWY + (_startH - newH)
            root.window.height = newH
        }
    }

    // ── Top-left corner ───────────────────────
    MouseArea {
        anchors { top: parent.top; left: parent.left }
        width: root.margin * 2; height: root.margin * 2
        cursorShape: Qt.SizeFDiagCursor
        property real _startGX: 0
        property real _startGY: 0
        property int  _startW:  0
        property int  _startH:  0
        property int  _startWX: 0
        property int  _startWY: 0
        onPressed: (m) => {
            var gp = mapToGlobal(m.x, m.y)
            _startGX = gp.x; _startGY = gp.y
            _startW  = root.window.width;  _startH  = root.window.height
            _startWX = root.window.x;      _startWY = root.window.y
        }
        onPositionChanged: (m) => {
            if (!pressed) return
            var gp = mapToGlobal(m.x, m.y)
            var dX = gp.x - _startGX
            var dY = gp.y - _startGY
            var newW = Math.max(960, _startW - dX)
            var newH = Math.max(640, _startH - dY)
            root.window.x      = _startWX + (_startW - newW)
            root.window.y      = _startWY + (_startH - newH)
            root.window.width  = newW
            root.window.height = newH
        }
    }
}
