"""Publisher-signature verification using Windows CNG (no bundled crypto library)."""
import ctypes
import hashlib
import json
import struct
import sys
from pathlib import Path

KEY_FILE = Path(__file__).parent / 'assets/update-key.json'


def load_key(path=KEY_FILE):
    key = json.loads(Path(path).read_text(encoding='utf-8'))
    modulus = key.get('modulus')
    if not modulus:
        raise ValueError('Automatic updates will be available with the first signed public release.')
    if key.get('algorithm') != 'RSA-PKCS1-SHA256' or key.get('exponent') != 65537:
        raise ValueError('Unsupported update signing key.')
    raw = bytes.fromhex(modulus)
    if len(raw) < 384 or len(raw) > 512 or not raw[0] & 0x80:
        raise ValueError('The update signing key must be RSA 3072–4096 bits.')
    return key


def verify_signature(message, signature, key):
    if sys.platform != 'win32':
        raise ValueError('Update signature verification requires Windows.')
    modulus = bytes.fromhex(key['modulus'])
    if len(signature) != len(modulus):
        raise ValueError('Invalid update signature.')
    exponent = key['exponent'].to_bytes(3, 'big')
    blob = struct.pack('<6I', 0x31415352, len(modulus) * 8, len(exponent), len(modulus), 0, 0) + exponent + modulus
    lib = ctypes.WinDLL('bcrypt', use_last_error=True)
    pointer, uint, status = ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long
    lib.BCryptOpenAlgorithmProvider.argtypes = [ctypes.POINTER(pointer), ctypes.c_wchar_p, ctypes.c_wchar_p, uint]
    lib.BCryptImportKeyPair.argtypes = [pointer, pointer, ctypes.c_wchar_p, ctypes.POINTER(pointer), pointer, uint, uint]
    lib.BCryptVerifySignature.argtypes = [pointer, pointer, pointer, uint, pointer, uint, uint]
    lib.BCryptDestroyKey.argtypes = [pointer]
    lib.BCryptCloseAlgorithmProvider.argtypes = [pointer, uint]
    for name in ('BCryptOpenAlgorithmProvider', 'BCryptImportKeyPair', 'BCryptVerifySignature',
                 'BCryptDestroyKey', 'BCryptCloseAlgorithmProvider'):
        getattr(lib, name).restype = status
    algorithm, public = pointer(), pointer()

    class Padding(ctypes.Structure):
        _fields_ = [('algorithm', ctypes.c_wchar_p)]

    try:
        if lib.BCryptOpenAlgorithmProvider(ctypes.byref(algorithm), 'RSA', None, 0):
            raise ValueError('Could not initialize Windows signature verification.')
        data = ctypes.create_string_buffer(blob)
        if lib.BCryptImportKeyPair(algorithm, None, 'RSAPUBLICBLOB', ctypes.byref(public), data, len(blob), 0):
            raise ValueError('Could not load the update signing key.')
        digest = ctypes.create_string_buffer(hashlib.sha256(message).digest())
        signed = ctypes.create_string_buffer(signature)
        padding = Padding('SHA256')
        if lib.BCryptVerifySignature(public, ctypes.byref(padding), digest, 32, signed, len(signature), 2):
            raise ValueError('The update publisher signature is invalid. Nothing has been installed.')
    finally:
        if public:
            lib.BCryptDestroyKey(public)
        if algorithm:
            lib.BCryptCloseAlgorithmProvider(algorithm, 0)
