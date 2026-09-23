import 'package:dio/dio.dart';
import '../../core/api/api_service.dart';
import '../../core/result.dart';

class UserProfile {
  final String username, role, firstName, lastName, email, phone;
  final String pendingEmail;
  final bool emailVerified, emailDeliveryFailed;
  const UserProfile({
    required this.username,
    required this.role,
    required this.firstName,
    required this.lastName,
    required this.email,
    required this.phone,
    this.pendingEmail = '',
    this.emailVerified = false,
    this.emailDeliveryFailed = false,
  });
  factory UserProfile.fromJson(Map<String, dynamic> json) => UserProfile(
    username: json['username'] as String,
    role: json['role'] as String,
    firstName: json['first_name'] as String,
    lastName: json['last_name'] as String,
    email: json['email'] as String,
    phone: json['phone'] as String,
    pendingEmail: json['pending_email'] as String? ?? '',
    emailVerified: json['email_verified'] as bool? ?? false,
    emailDeliveryFailed: json['email_delivery_failed'] as bool? ?? false,
  );
}

class ProfileRepository {
  final ApiService api;
  ProfileRepository(this.api);
  Future<Result<UserProfile>> load() => _request();
  Future<Result<UserProfile>> save(Map<String, String> values) =>
      _request(values);
  Future<Result<UserProfile>> _request([Map<String, String>? values]) async {
    try {
      final data = await api.request(
        'profile/',
        method: values == null ? 'GET' : 'PATCH',
        data: values,
      );
      return Success(UserProfile.fromJson(data));
    } catch (error) {
      if (error is DioException &&
          error.response?.statusCode == 400 &&
          error.response?.data is Map) {
        final fields = error.response!.data as Map;
        return Failure(
          fields.values
              .map((value) => value is List ? value.join(' ') : '$value')
              .join('\n'),
        );
      }
      return Failure(describeError(error));
    }
  }
}
