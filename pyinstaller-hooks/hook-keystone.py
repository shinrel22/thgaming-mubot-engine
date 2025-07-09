# hooks/hook-keystone.py
from PyInstaller.utils.hooks import collect_dynamic_libs

binaries = collect_dynamic_libs('keystone')
