// qml/Sidebar.qml
// ────────────────
// Left navigation sidebar — premium cybersecurity dark theme.
// Refined: depth/surface layering, active-item glow pill, section hierarchy,
// spacing rhythm, utility buttons, and full backend-integration preserved.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic

Rectangle {
    id: root
    width: Theme.sidebarWidth
    color: "transparent"   // outer wrapper is transparent; inner panel provides depth

    // ── Signals ───────────────────────────────
    signal auditLogAction()
    signal changePasswordAction()
    signal healthDashboardAction()
    signal recoveryKeysAction()
    signal filterChanging()

    // ── State ─────────────────────────────────
    property var _tags:       []
    property var _categories: []

    function refreshTags() {
        root._tags = vault.getAllTags()
        tagRepeater.model = root._tags
    }
    function refreshCategories() {
        root._categories = vault.getAllCategories()
        catRepeater.model = root._categories
    }

    Connections {
        target: vault
        function onTagsChanged()       { root.refreshTags() }
        function onCategoriesChanged() { root.refreshCategories() }
        function onEntriesChanged()    { root.refreshTags(); root.refreshCategories() }
        function onLockStateChanged()  { if (!vault.isLocked) { root.refreshTags(); root.refreshCategories() } }
    }
    Component.onCompleted: if (!vault.isLocked) { refreshTags(); refreshCategories() }

    // ══════════════════════════════════════════
    // Panel surface — layered depth
    // ══════════════════════════════════════════
    Rectangle {
        id: panelSurface
        anchors.fill: parent

        // Base panel colour
        color: Theme.sidebarBg

        // Right border — subtle separation line
        Rectangle {
            anchors { top: parent.top; bottom: parent.bottom; right: parent.right }
            width: 1
            color: Theme.bgBorder
            opacity: 0.7
        }

        // Very subtle top gradient bloom for depth
        Rectangle {
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 120
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(91/255, 192/255, 255/255, 0.04) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }

    // ══════════════════════════════════════════
    // Scrollable content column
    // ══════════════════════════════════════════
    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.topMargin: 0
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical: ScrollBar {
            width: 4
            policy: ScrollBar.AsNeeded
            contentItem: Rectangle {
                implicitWidth: 4
                radius: 2
                color: Theme.textMuted
                opacity: 0.4
            }
            background: Item {}
        }

        ColumnLayout {
            width: root.width
            spacing: 0

            // ── Top padding ───────────────────
            Item { height: 12 }

            // ══════════════════════════════════
            // SECTION: VAULT
            // ══════════════════════════════════
            SidebarSection {
                label: "VAULT"
                Layout.fillWidth: true
            }

            Item { height: 4 }

            NavItem {
                Layout.fillWidth: true
                label:  "All Entries"
                icon:   "⊞"
                active: vault.currentFilter === "all"
                onClicked: { root.filterChanging(); vault.setFilter("all") }
            }

            Item { height: 2 }

            NavItem {
                Layout.fillWidth: true
                label:  "Favourites"
                icon:   "★"
                active: vault.currentFilter === "favorites"
                onClicked: { root.filterChanging(); vault.setFilter("favorites") }
            }

            Item { height: 12 }
            SidebarDivider { Layout.fillWidth: true }
            Item { height: 12 }

            // ══════════════════════════════════
            // SECTION: CATEGORIES
            // ══════════════════════════════════
            SidebarSection {
                label: "CATEGORIES"
                Layout.fillWidth: true
            }

            Item { height: 4 }

            // Category list
            ColumnLayout {
                id: catCol
                Layout.fillWidth: true
                spacing: 2

                Repeater {
                    id: catRepeater
                    model: root._categories

                    NavItem {
                        required property string modelData
                        Layout.fillWidth: true
                        label:  modelData
                        active: vault.currentFilter === "category" && vault.currentCategory === modelData
                        showCategoryIcon: true
                        onClicked: { root.filterChanging(); vault.setCategoryFilter(modelData) }
                    }
                }

                Text {
                    visible:        root._categories.length === 0
                    text:           "No categories yet"
                    color:          Theme.textMuted
                    font.family:    Theme.fontFamily
                    font.pointSize: Theme.fontSizeSM
                    leftPadding: 20
                    topPadding: 4
                    font.italic: true
                }
            }

            // ── Utility action row ────────────
            Item { height: 10 }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 12
                Layout.rightMargin: 12
                spacing: 6

                ActionPill {
                    id: autoCatBtn
                    Layout.fillWidth: true
                    label:     isRunning ? "Working…" : "✨ Auto-tag"
                    isLoading: isRunning
                    property bool isRunning: false
                    interactive: !isRunning
                    onClicked: vault.autoCategorizeAll()
                    Connections {
                        target: vault
                        function onAutoCategorizeStarted()      { autoCatBtn.isRunning = true }
                        function onAutoCategorizeFinished(u, t) { autoCatBtn.isRunning = false }
                    }
                }

                ActionPill {
                    id: cleanNamesBtn
                    Layout.fillWidth: true
                    label:     isRunning ? "Working…" : "🧹 Clean"
                    isLoading: isRunning
                    property bool isRunning: false
                    interactive: !isRunning
                    onClicked: confirmCleanPopup.open()
                    Connections {
                        target: vault
                        function onNormalizeStarted()      { cleanNamesBtn.isRunning = true }
                        function onNormalizeFinished(u, t) { cleanNamesBtn.isRunning = false }
                    }
                }
            }

            Item { height: 12 }
            SidebarDivider { Layout.fillWidth: true }
            Item { height: 12 }

            // ══════════════════════════════════
            // SECTION: TAGS
            // ══════════════════════════════════
            SidebarSection {
                label: "TAGS"
                Layout.fillWidth: true
            }

            Item { height: 4 }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Repeater {
                    id: tagRepeater
                    model: root._tags

                    NavItem {
                        required property string modelData
                        Layout.fillWidth: true
                        label:  modelData
                        icon:   "🏷"
                        active: vault.currentFilter === "tag" && vault.currentTag === modelData
                        onClicked: { root.filterChanging(); vault.setTagFilter(modelData) }
                    }
                }

                Text {
                    visible:        root._tags.length === 0
                    text:           "No tags yet"
                    color:          Theme.textMuted
                    font.family:    Theme.fontFamily
                    font.pointSize: Theme.fontSizeSM
                    leftPadding: 20
                    topPadding: 4
                    font.italic: true
                }
            }

            Item { height: 12 }
            SidebarDivider { Layout.fillWidth: true }
            Item { height: 12 }

            // ══════════════════════════════════
            // SECTION: TOOLS
            // ══════════════════════════════════
            SidebarSection {
                label: "TOOLS"
                Layout.fillWidth: true
            }

            Item { height: 4 }

            NavItem {
                Layout.fillWidth: true
                icon: "🛡"
                label: "Health Dashboard"
                onClicked: root.healthDashboardAction()
            }
            Item { height: 2 }
            NavItem {
                Layout.fillWidth: true
                icon: "📋"
                label: "Audit Log"
                onClicked: root.auditLogAction()
            }
            Item { height: 2 }
            NavItem {
                Layout.fillWidth: true
                icon: "🔑"
                label: "Change Password"
                onClicked: root.changePasswordAction()
            }
            Item { height: 2 }
            NavItem {
                Layout.fillWidth: true
                icon: "🛟"
                label: "Recovery Keys"
                onClicked: root.recoveryKeysAction()
            }

            // ── Bottom breathing room ─────────
            Item { height: 24 }
        }
    }

    // ══════════════════════════════════════════
    // Clean-names confirmation popup
    // ══════════════════════════════════════════
    Popup {
        id: confirmCleanPopup
        x: Math.round((root.width - width) / 2)
        y: Math.round((root.height - height) / 2)
        width: 290; padding: 0
        modal: true; dim: true
        background: Rectangle {
            color: Theme.bgSurface
            border.color: Theme.bgBorder
            radius: Theme.radiusLG
            // subtle inner shadow ring
            Rectangle {
                anchors.fill: parent; anchors.margins: -1
                radius: parent.radius + 1; color: "transparent"
                border.color: Theme.accentGlow; border.width: 1; z: -1
            }
        }
        Overlay.modal: Rectangle { color: Theme.bgOverlay }

        contentItem: ColumnLayout {
            spacing: 0

            // Header strip
            Rectangle {
                Layout.fillWidth: true; height: 48
                color: Theme.bgSurface2; radius: Theme.radiusLG
                Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: Theme.bgBorder }
                Text {
                    anchors.centerIn: parent
                    text: "Clean Site Names?"
                    color: Theme.textPrimary; font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeMD; font.weight: Font.DemiBold
                }
            }

            // Body
            ColumnLayout {
                Layout.margins: 20; spacing: 16
                Text {
                    Layout.fillWidth: true
                    text: "This will normalize all raw hostnames\ninto clean brand names."
                    color: Theme.textSecondary; font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeSM; lineHeight: 1.4
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    // Cancel
                    Rectangle {
                        width: 80; height: 32; radius: Theme.radiusSM
                        color: cancelMa.containsMouse ? Theme.bgSurface3 : Theme.bgSurface2
                        border.color: Theme.bgBorder
                        Behavior on color { ColorAnimation { duration: Theme.animFast } }
                        Text { anchors.centerIn: parent; text: "Cancel"; color: Theme.textSecondary; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM }
                        MouseArea { id: cancelMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true; onClicked: confirmCleanPopup.close() }
                    }
                    // Confirm
                    Rectangle {
                        width: 88; height: 32; radius: Theme.radiusSM
                        color: confirmMa.containsMouse ? Theme.accentHover : Theme.accent
                        Behavior on color { ColorAnimation { duration: Theme.animFast } }
                        Text { anchors.centerIn: parent; text: "Confirm"; color: "#fff"; font.family: Theme.fontFamily; font.pointSize: Theme.fontSizeSM; font.weight: Font.DemiBold }
                        MouseArea { id: confirmMa; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true; onClicked: { vault.normalizeAllSiteNames(); confirmCleanPopup.close() } }
                    }
                }
            }
        }
    }

    // ══════════════════════════════════════════
    // Reusable sub-components
    // ══════════════════════════════════════════

    // ── Section header label ──────────────────
    component SidebarSection: Item {
        property string label: ""
        implicitHeight: 20
        Layout.leftMargin: 0

        Text {
            anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter }
            text: label
            color: Theme.sidebarSectionLabel
            font.family:     Theme.fontFamily
            font.pointSize:  Theme.fontSizeXS
            font.weight:     Font.Bold
            font.letterSpacing: 1.6
        }
    }

    // ── Horizontal divider ────────────────────
    component SidebarDivider: Rectangle {
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        height: 1
        color: Theme.bgBorder
        opacity: 0.5
    }

    // ── Navigation item ───────────────────────
    component NavItem: Rectangle {
        id: navItemRoot
        property string label:            ""
        property string icon:             ""
        property bool   active:           false
        property bool   showCategoryIcon: false
        signal clicked()

        implicitHeight: 34
        Layout.leftMargin: 8
        Layout.rightMargin: 8
        radius: Theme.radiusSM

        // Base fill — hover / active states
        color: {
            if (active)          return Theme.navActiveBg
            if (ma.containsMouse) return Theme.navHoverBg
            return "transparent"
        }
        Behavior on color { ColorAnimation { duration: Theme.animFast } }

        // Active: subtle outer glow ring
        Rectangle {
            anchors.fill:    parent
            anchors.margins: -1
            radius:          parent.radius + 1
            color:           "transparent"
            border.color:    navItemRoot.active ? Theme.navGlow : "transparent"
            border.width:    1
            z: -1
            Behavior on border.color { ColorAnimation { duration: Theme.animFast } }
        }

        // Left accent pill — active indicator
        Rectangle {
            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
            anchors.leftMargin: 0
            width:  3
            height: navItemRoot.active ? 20 : 0
            radius: 2
            color:  Theme.cyan
            Behavior on height { NumberAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic } }
            Behavior on color  { ColorAnimation  { duration: Theme.animFast } }
        }

        RowLayout {
            anchors {
                left:  parent.left;  leftMargin:  14
                right: parent.right; rightMargin: 12
                verticalCenter: parent.verticalCenter
            }
            spacing: 8

            // Icon — emoji or placeholder
            Text {
                visible:        navItemRoot.icon !== "" || navItemRoot.showCategoryIcon
                text:           navItemRoot.icon !== "" ? navItemRoot.icon : "📁"
                font.pointSize: Theme.fontSizeSM
                color: navItemRoot.active ? Theme.cyan : Theme.textMuted
                Behavior on color { ColorAnimation { duration: Theme.animFast } }
            }

            // Label
            Text {
                Layout.fillWidth: true
                text:  navItemRoot.label
                color: navItemRoot.active
                       ? Theme.navActiveText
                       : ma.containsMouse ? Theme.textPrimary : Theme.navText
                font.family:    Theme.fontFamily
                font.pointSize: Theme.fontSizeSM
                font.weight:    navItemRoot.active ? Font.DemiBold : Font.Normal
                elide:          Text.ElideRight
                Behavior on color { ColorAnimation { duration: Theme.animFast } }
            }

            // Active dot badge
            Rectangle {
                visible:  navItemRoot.active
                width: 6; height: 6; radius: 3
                color: Theme.cyan
                opacity: 0.8
            }
        }

        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape:  Qt.PointingHandCursor
            onClicked:    navItemRoot.clicked()
        }

        Accessible.role: Accessible.Button
        Accessible.name: navItemRoot.label
        Accessible.onPressAction: navItemRoot.clicked()
    }

    // ── Utility action pill button ────────────
    component ActionPill: Rectangle {
        id: pillRoot
        property string label:       ""
        property bool   interactive: true
        property bool   isLoading:   false
        signal clicked()

        implicitHeight: 28
        radius: Theme.radiusSM
        color: {
            if (!interactive)        return Theme.bgSurface2
            if (pMa.containsMouse)   return Theme.bgSurface3
            return Theme.bgSurface
        }
        border.color: {
            if (!interactive)      return Theme.bgBorder
            if (pMa.containsMouse) return Qt.rgba(91/255, 192/255, 255/255, 0.35)
            return Theme.bgBorder
        }
        border.width: 1
        opacity: interactive ? 1.0 : 0.55

        Behavior on color        { ColorAnimation { duration: Theme.animFast } }
        Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

        RowLayout {
            anchors.centerIn: parent
            spacing: 4

            // Spinner dot when loading
            Rectangle {
                visible: pillRoot.isLoading
                width: 6; height: 6; radius: 3
                color: Theme.cyan
                SequentialAnimation on opacity {
                    running: pillRoot.isLoading
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.2; duration: 500 }
                    NumberAnimation { to: 1.0; duration: 500 }
                }
            }

            Text {
                text:  pillRoot.label
                color: pillRoot.interactive
                       ? (pMa.containsMouse ? Theme.textPrimary : Theme.textSecondary)
                       : Theme.textMuted
                font.family:    Theme.fontFamily
                font.pointSize: Theme.fontSizeXS
                font.weight:    Font.Medium
                Behavior on color { ColorAnimation { duration: Theme.animFast } }
            }
        }

        MouseArea {
            id: pMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape:  pillRoot.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked:    if (pillRoot.interactive) pillRoot.clicked()
        }
    }
}
