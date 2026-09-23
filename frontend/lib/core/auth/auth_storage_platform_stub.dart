import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'auth_storage_base.dart';

AuthStorage createPlatformAuthStorage() => SecureAuthStorage(
  const FlutterSecureStorage(webOptions: WebOptions(useSessionStorage: true)),
);
