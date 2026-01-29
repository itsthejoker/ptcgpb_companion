from PyInstaller.utils.hooks import collect_data_files, collect_submodules

EXCLUDES = [
    "**/*.mo",
    "**/*.po",
    "**/LC_MESSAGES/**",
]

datas = collect_data_files("django", excludes=EXCLUDES)
hiddenimports = collect_submodules("django")
