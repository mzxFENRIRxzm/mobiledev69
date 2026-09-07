import 'package:dio/dio.dart';

import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;

class ApiService {
  // ใช้ 10.0.2.2 สำหรับ Android Emulator, และ 127.0.0.1 สำหรับ Windows/Web/iOS Simulator
  static String get baseUrl {
    if (kIsWeb) return 'http://127.0.0.1:8000';
    if (Platform.isAndroid) return 'http://10.0.2.2:8000';
    return 'http://127.0.0.1:8000';
  }

  final Dio _dio;
  String? _accessToken;
  String? _refreshToken;

  ApiService()
      : _dio = Dio(
          BaseOptions(
            baseUrl: baseUrl,
            connectTimeout: const Duration(seconds: 10),
            receiveTimeout: const Duration(seconds: 10),
            headers: {
              'Content-Type': 'application/json',
            },
          ),
        );

  bool get isLoggedIn => _accessToken != null;
  String? get accessToken => _accessToken;
  String? get refreshToken => _refreshToken;

  /// Login ด้วย username/password แล้วได้ JWT token กลับมา
  Future<Map<String, dynamic>> login(String username, String password) async {
    try {
      final response = await _dio.post(
        '/api/token/',
        data: {
          'username': username,
          'password': password,
        },
      );

      _accessToken = response.data['access'];
      _refreshToken = response.data['refresh'];

      // เพิ่ม Authorization header สำหรับ request ต่อๆ ไป
      _dio.options.headers['Authorization'] = 'Bearer $_accessToken';

      return {
        'success': true,
        'data': response.data,
      };
    } on DioException catch (e) {
      return {
        'success': false,
        'error': e.response?.data?['detail'] ?? 'เชื่อมต่อเซิร์ฟเวอร์ไม่ได้',
      };
    }
  }

  /// Refresh access token
  Future<bool> refreshAccessToken() async {
    if (_refreshToken == null) return false;

    try {
      final response = await _dio.post(
        '/api/token/refresh/',
        data: {'refresh': _refreshToken},
      );

      _accessToken = response.data['access'];
      _dio.options.headers['Authorization'] = 'Bearer $_accessToken';
      return true;
    } catch (e) {
      return false;
    }
  }

  /// ดึงรายการ Bookings
  Future<Map<String, dynamic>> getBookings() async {
    try {
      final response = await _dio.get('/api/bookings/');
      return {
        'success': true,
        'data': response.data,
      };
    } on DioException catch (e) {
      // ถ้า 401 ลอง refresh token
      if (e.response?.statusCode == 401) {
        final refreshed = await refreshAccessToken();
        if (refreshed) {
          return getBookings(); // retry
        }
      }
      return {
        'success': false,
        'error': e.response?.data?['detail'] ?? 'ไม่สามารถดึงข้อมูลได้',
      };
    }
  }

  /// Logout
  void logout() {
    _accessToken = null;
    _refreshToken = null;
    _dio.options.headers.remove('Authorization');
  }
}
