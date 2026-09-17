import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'auth_view_model.dart';

class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthViewModel>();
    return Scaffold(
      backgroundColor: const Color(0xff101214),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Container(
              padding: const EdgeInsets.all(28),
              decoration: BoxDecoration(
                color: const Color(0xff1b1e22),
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: const Color(0xff35383e)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  const Text(
                    'THE_X',
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 6,
                      color: Color(0xffe9bd69),
                    ),
                  ),
                  const SizedBox(height: 32),
                  Icon(
                    Icons.two_wheeler,
                    size: 64,
                    color: const Color(0xffe9bd69),
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'ยินดีต้อนรับกลับ',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      height: 1.3,
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'เข้าสู่บัญชี THE_X ของคุณ\nเพื่อดูแลรถ จองซ่อม และติดตามงาน',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 15,
                      height: 1.8,
                      color: Color(0xffaaadb3),
                    ),
                  ),
                  const SizedBox(height: 36),
                  if (auth.error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: Text(
                        auth.error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xffc93832),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                      onPressed: auth.loading ? null : auth.login,
                      icon: const Icon(Icons.arrow_forward),
                      label: const Padding(
                        padding: EdgeInsets.all(16),
                        child: Text('เข้าสู่ระบบ THE_X'),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'กรอกชื่อผู้ใช้และรหัสผ่านในหน้าถัดไป\nระบบจะเปิดหน้าที่ตรงกับบทบาทของคุณ',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Color(0xffaaadb3),
                      fontSize: 12,
                      height: 1.7,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
