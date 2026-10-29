"""Real icon grid filtering, keyboard selection and original SVG rendering."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from bashdock import tab_icons
from bashdock.tab_icon_catalog import CATALOG, GENERIC, KEYWORDS
from bashdock.tab_icon_picker import TabIconPicker
from qt_lifecycle import GuiTestCase


class TabIconPickerTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.picker = TabIconPicker('server')

    def tearDown(self):
        self.picker.close()
        self.picker.deleteLater()

    def visible(self):
        return {self.picker.icons.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.picker.icons.count()) if not self.picker.icons.item(i).isHidden()}

    def test_expanded_catalog_renders_and_keeps_the_original_automatic_shapes(self):
        self.assertEqual(96, len(CATALOG))
        self.assertEqual(set(CATALOG), set(KEYWORDS))
        self.assertEqual(['circle', 'diamond', 'square', 'triangle', 'hexagon', 'star',
                          'cross', 'pentagon', 'rings', 'grid', 'target', 'cube'], list(GENERIC))
        for key, (label, body) in CATALOG.items():
            with self.subTest(icon=key):
                svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{body}</svg>'
                self.assertTrue(QSvgRenderer(QByteArray(svg.encode())).isValid())
                self.assertFalse(tab_icons.icon(key).pixmap(18, 18).isNull())

    def test_live_search_matches_names_aliases_case_and_multiple_terms_without_enter(self):
        self.picker.search.setText('sSh')
        self.assertEqual({'terminal', 'server', 'key'}, self.visible())
        self.assertEqual('server', self.picker.selected_icon())
        self.picker.search.setText('  GIT   REVIEW ')
        self.assertEqual({'pull-request'}, self.visible())
        self.assertIsNone(self.picker.selected_icon())
        self.picker.search.setText('container')
        self.assertEqual({'containers'}, self.visible())
        self.picker.search.setText('PYTHON')
        self.assertTrue({'code', 'script', 'flask'} <= self.visible())

    def test_no_match_cannot_accept_hidden_selection_and_clear_restores_choice(self):
        self.picker.show()
        self.app.processEvents()
        self.picker.search.setText('nothing matches this query')
        self.assertEqual(set(), self.visible())
        self.assertTrue(self.picker.empty_state.isVisible())
        self.assertFalse(self.picker.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        self.picker.accept()
        self.assertEqual(QDialog.DialogCode.Rejected, self.picker.result())
        self.assertTrue(self.picker.isVisible())
        QTest.keyClick(self.picker.search, Qt.Key.Key_Return)
        self.assertTrue(self.picker.isVisible())
        self.picker.search.clear()
        self.assertEqual(set(CATALOG), self.visible())
        self.assertEqual('server', self.picker.selected_icon())
        self.assertFalse(self.picker.empty_state.isVisible())
        self.assertTrue(self.picker.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())

    def test_keyboard_search_down_and_enter_select_visible_result_and_escape_cancels(self):
        self.picker.show()
        self.picker.activateWindow()
        self.app.processEvents()
        self.assertIs(self.picker.search, self.picker.focusWidget())
        QTest.keyClicks(self.picker.search, 'robot')
        self.assertEqual({'robot'}, self.visible())
        QTest.keyClick(self.picker.search, Qt.Key.Key_Down)
        self.assertIs(self.picker.icons, self.picker.focusWidget())
        self.assertEqual('robot', self.picker.selected_icon())
        self.picker.search.clear()
        self.assertEqual('robot', self.picker.selected_icon())
        QTest.keyClick(self.picker.icons, Qt.Key.Key_Return)
        self.assertEqual(QDialog.DialogCode.Accepted, self.picker.result())
        self.picker.show()
        self.picker.search.setFocus()
        QTest.keyClick(self.picker.search, Qt.Key.Key_Escape)
        self.assertFalse(self.picker.isVisible())
        self.assertEqual(QDialog.DialogCode.Rejected, self.picker.result())
