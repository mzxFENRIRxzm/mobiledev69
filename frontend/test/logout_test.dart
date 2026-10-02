import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:the_x/core/auth/auth_service.dart';
import 'package:the_x/core/api/api_service.dart';
import 'package:the_x/core/result.dart';
import 'package:the_x/features/auth/auth_repository.dart';

class LogoutAuth extends AuthService {
  LogoutAuth() : super(const FlutterSecureStorage());
  bool cleared = false;
  @override
  Uri? logoutUri() => null;
  @override
  Future<void> clear() async {
    cleared = true;
  }
}

class LogoutApi extends ApiService {
  LogoutApi(super.auth, this.status);
  final int status;
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Object? data,
  }) async {
    final options = RequestOptions(path: path);
    throw DioException(
      requestOptions: options,
      response: Response(requestOptions: options, statusCode: status),
    );
  }
}

void main() {
  test(
    'revoked session can logout locally; server failure remains distinguishable',
    () async {
      final auth = LogoutAuth();
      expect(
        await AuthRepository(auth, LogoutApi(auth, 401)).logout(),
        isA<Success<void>>(),
      );
      expect(auth.cleared, isTrue);
      final unavailable = LogoutAuth();
      expect(
        await AuthRepository(unavailable, LogoutApi(unavailable, 502)).logout(),
        isA<Failure<void>>(),
      );
      expect(unavailable.cleared, isFalse);
    },
  );
}
