import ctypes


def LPVOID_errcheck(result, func, args):
    if result is None:
        raise ctypes.WinError(ctypes.get_last_error())
    return result


def Win32API_errcheck(result, func, args):
    if result is None:
        raise ctypes.WinError(ctypes.get_last_error())
    return result

def VirtualQueryEx_errcheck(result, func, args):
    if result is None:
        raise ctypes.WinError(ctypes.get_last_error())
    return result

