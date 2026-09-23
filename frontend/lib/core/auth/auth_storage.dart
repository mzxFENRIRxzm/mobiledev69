import 'auth_storage_base.dart';
import 'auth_storage_platform_stub.dart'
    if (dart.library.html) 'auth_storage_platform_web.dart' as platform;

export 'auth_storage_base.dart';

AuthStorage createAuthStorage() => platform.createPlatformAuthStorage();
