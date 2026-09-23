import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract interface class AuthStorage {
  Future<String?> read({required String key});
  Future<void> write({required String key, required String? value});
  Future<void> delete({required String key});
}

class SecureAuthStorage implements AuthStorage {
  final FlutterSecureStorage _storage;
  const SecureAuthStorage(this._storage);

  @override
  Future<String?> read({required String key}) => _storage.read(key: key);

  @override
  Future<void> write({required String key, required String? value}) =>
      _storage.write(key: key, value: value);

  @override
  Future<void> delete({required String key}) => _storage.delete(key: key);
}
