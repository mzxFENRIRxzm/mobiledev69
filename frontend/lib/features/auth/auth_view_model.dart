import 'package:flutter/foundation.dart';
import '../../core/result.dart';
import 'auth_repository.dart';

class AuthViewModel extends ChangeNotifier {
  final AuthRepository repository;
  bool loading = true;
  AppUser? user;
  String? get username => user?.username;
  bool get isMechanic => user?.role == 'mechanic';
  bool get isAdmin => user?.role == 'admin';
  String? error;
  AuthViewModel(this.repository);
  Future<void> restore(Uri location) async {
    final result = await repository.restore(location);
    if (result is Success<AppUser?>) user = result.value;
    if (result is Failure<AppUser?>) error = result.message;
    loading = false;
    notifyListeners();
  }

  Future<void> login() async {
    loading = true;
    error = null;
    notifyListeners();
    final result = await repository.login();
    if (result is Failure<void>) error = result.message;
    loading = false;
    notifyListeners();
  }

  Future<void> logout() async {
    loading = true;
    error = null;
    notifyListeners();
    final result = await repository.logout();
    if (result is Failure<void>) {
      error = result.message;
    } else {
      user = null;
    }
    loading = false;
    notifyListeners();
  }
}
