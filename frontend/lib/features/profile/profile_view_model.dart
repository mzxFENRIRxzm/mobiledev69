import 'package:flutter/foundation.dart';
import '../../core/result.dart';
import 'profile_repository.dart';

class ProfileViewModel extends ChangeNotifier {
  final ProfileRepository repository;
  ProfileViewModel(this.repository);
  UserProfile? profile;
  bool loading = false, saving = false, _disposed = false;
  String? error, message;
  void _notify() {
    if (!_disposed) notifyListeners();
  }

  Future<void> load() async {
    if (loading || saving) return;
    loading = true;
    error = null;
    message = null;
    _notify();
    final result = await repository.load();
    if (_disposed) return;
    if (result is Success<UserProfile>) profile = result.value;
    if (result is Failure<UserProfile>) error = result.message;
    loading = false;
    _notify();
  }

  Future<void> save(Map<String, String> values) async {
    if (loading || saving) return;
    saving = true;
    error = null;
    message = null;
    _notify();
    final result = await repository.save(values);
    if (_disposed) return;
    if (result is Success<UserProfile>) {
      profile = result.value;
      message = profile!.emailDeliveryFailed
          ? 'บันทึกโปรไฟล์แล้ว แต่ส่งอีเมลยืนยันไม่สำเร็จ กรุณาขอส่งลิงก์อีกครั้ง'
          : profile!.pendingEmail.isNotEmpty
              ? 'บันทึกแล้ว กรุณายืนยันอีเมลใหม่ก่อนใช้งาน'
              : 'บันทึกโปรไฟล์แล้ว';
    }
    if (result is Failure<UserProfile>) error = result.message;
    saving = false;
    _notify();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
