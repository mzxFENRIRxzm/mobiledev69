import 'package:dio/dio.dart';
import '../auth/auth_service.dart';
import '../config.dart';

class ApiService {
  final AuthService auth;
  final Dio _dio = Dio(
    BaseOptions(
      baseUrl: '$apiBase/api/',
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 30),
    ),
  );
  ApiService(this.auth);
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Object? data,
  }) async {
    final token = await auth.accessToken();
    final response = await _dio.request(
      path,
      data: data,
      options: Options(
        method: method,
        headers: {'Authorization': 'Bearer $token'},
      ),
    );
    return response.data;
  }
}

String describeError(Object error) {
  if (error is DioException) {
    if (error.response?.statusCode == 401) {
      return 'เซสชันหมดอายุ กรุณาออกจากระบบแล้วเข้าสู่ระบบใหม่';
    }
    if (error.response?.statusCode == 400) {
      return 'ตรวจสอบข้อมูลอีกครั้ง: ${error.response?.data}';
    }
    if (error.response?.statusCode == 404) {
      return 'ไม่พบรายการนี้ กรุณาโหลดข้อมูลใหม่';
    }
    if ([403, 409].contains(error.response?.statusCode)) {
      return '${error.response?.data['detail'] ?? 'ไม่มีสิทธิ์ดำเนินการ กรุณาโหลดข้อมูลใหม่'}';
    }
    return 'เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาลองใหม่อีกครั้ง';
  }
  return 'ดำเนินการไม่สำเร็จ กรุณาลองเข้าสู่ระบบใหม่';
}
