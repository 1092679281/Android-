import unittest
from apply_r6_ui import once, tag_attr, view_ids, new_outline, add_color

class AdversarialUiPatchTests(unittest.TestCase):
    def test_anchor_must_be_unique(self):
        with self.assertRaises(ValueError):
            once("id id", "id", "updated", "collision")

    def test_missing_anchor_must_fail(self):
        with self.assertRaises(ValueError):
            once("hello", "not-found", "updated", "missing")

    def test_only_specific_view_changes(self):
        xml = ('<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android">'
               '<TextView android:id="@+id/first" android:layout_height="30dp" />'
               '<TextView android:id="@+id/second" android:layout_height="30dp" />'
               '</LinearLayout>')
        changed = tag_attr(xml, "first", 'android:layout_height="30dp"',
                           'android:layout_height="48dp"')
        self.assertEqual(view_ids(xml), view_ids(changed))
        self.assertEqual(changed.count('android:layout_height="30dp"'), 1)
        self.assertEqual(changed.count('android:layout_height="48dp"'), 1)

    def test_invalid_layout_pattern_is_blocked(self):
        with self.assertRaises(ValueError):
            new_outline('<shape><solid android:color="@color/ui_card" /></shape>')

    def test_duplicate_color_token_is_blocked(self):
        with self.assertRaises(ValueError):
            add_color('<resources><color name="ui_card_outline">#CCC</color></resources>', "#EEE")

    def test_duplicate_view_id_is_blocked(self):
        xml = ('<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android">'
               '<TextView android:id="@+id/same" />'
               '<TextView android:id="@+id/same" />'
               '</LinearLayout>')
        with self.assertRaises(ValueError):
            view_ids(xml)

if __name__ == "__main__":
    unittest.main()
