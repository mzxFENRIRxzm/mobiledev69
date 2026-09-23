// ignore_for_file: deprecated_member_use, avoid_web_libraries_in_flutter
import 'dart:html' as html;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'auth_storage_base.dart';

const _allowInsecureLanStorage = bool.fromEnvironment(
  'ALLOW_INSECURE_LAN_STORAGE',
  defaultValue: false,
);

AuthStorage createPlatformAuthStorage() {
  if (_allowInsecureLanStorage && html.window.isSecureContext != true) {
    return const LanSessionStorage();
  }
  return SecureAuthStorage(
    const FlutterSecureStorage(webOptions: WebOptions(useSessionStorage: true)),
  );
}

class LanSessionStorage implements AuthStorage {
  const LanSessionStorage();
  static const _prefix = 'FlutterSecureStorage.';

  @override
  Future<String?> read({required String key}) async =>
      html.window.sessionStorage['$_prefix$key'];

  @override
  Future<void> write({required String key, required String? value}) async {
    final storageKey = '$_prefix$key';
    if (value == null) {
      html.window.sessionStorage.remove(storageKey);
    } else {
      html.window.sessionStorage[storageKey] = value;
    }
  }

  @override
  Future<void> delete({required String key}) async =>
      html.window.sessionStorage.remove('$_prefix$key');
}
