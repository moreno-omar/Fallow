This plugin does not support propagateSizeHints()
Traceback (most recent call last):
  File "/tmp/debug_palette.py", line 37, in <module>
    sys.exit(main())
  File "/tmp/debug_palette.py", line 21, in main
    print("matches for 'zoom':", [item.data(256).title for item in palette.result_list.findItems("*", 0)])
TypeError: 'PySide6.QtWidgets.QListWidget.findItems' called with wrong argument types:
  PySide6.QtWidgets.QListWidget.findItems(str, int)
Supported signatures:
  PySide6.QtWidgets.QListWidget.findItems(text: str, flags: PySide6.QtCore.Qt.MatchFlag, /)