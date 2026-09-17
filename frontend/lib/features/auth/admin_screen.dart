import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/config.dart';
import 'auth_view_model.dart';

class AdminScreen extends StatelessWidget {
  const AdminScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthViewModel>();
    return Scaffold(
      appBar: AppBar(
        title: Text('THE_X · Admin · ${auth.username}'),
        actions: [
          TextButton(
            onPressed: auth.loading ? null : auth.logout,
            child: const Text('ออกจากระบบทุกอุปกรณ์'),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('จัดการระบบ', style: TextStyle(fontSize: 30)),
                const SizedBox(height: 16),
                const Text(
                  'จัดการผู้ใช้และเลือกบทบาท Adminuser, Mechanicuser หรือ Customeruser ผ่าน Django admin แล้วกำหนดร้านให้ช่างใน Shops',
                ),
                const SizedBox(height: 20),
                FilledButton.icon(
                  onPressed: () async {
                    final opened = await launchUrl(
                      Uri.parse('$apiBase/admin/auth/user/'),
                      webOnlyWindowName: '_blank',
                    );
                    if (!opened && context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('เปิดหน้าจัดการไม่ได้ กรุณาลองใหม่'),
                        ),
                      );
                    }
                  },
                  icon: const Icon(Icons.manage_accounts),
                  label: const Text('จัดการผู้ใช้และบทบาท'),
                ),
                if (auth.error != null) Text(auth.error!),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
