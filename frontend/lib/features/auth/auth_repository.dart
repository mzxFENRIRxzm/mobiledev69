import '../../core/api/api_service.dart';
import '../../core/auth/auth_service.dart';
import '../../core/result.dart';

class AppUser {
  final String username;
  final String role;
  const AppUser(this.username, this.role);
}

class AuthRepository {
  final AuthService auth;
  final ApiService api;
  AuthRepository(this.auth, this.api);
  Future<Result<AppUser?>> restore(Uri location) async {
    try {
      if (!await auth.restore(location)) return const Success(null);
      final user = await api.request('me/');
      return Success(
        AppUser(user['username'] as String, user['role'] as String),
      );
    } catch (e) {
      return Failure(describeError(e));
    }
  }

  Future<Result<void>> login() async {
    try {
      await auth.login();
      return const Success(null);
    } catch (e) {
      return Failure(describeError(e));
    }
  }

  Future<Result<void>> logout() async {
    try {
      final uri = auth.logoutUri();
      await api.request('logout/', method: 'POST');
      await auth.clear();
      await auth.endProviderSession(uri);
      return const Success(null);
    } catch (e) {
      return Failure(describeError(e));
    }
  }
}
