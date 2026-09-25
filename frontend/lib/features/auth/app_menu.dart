import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'auth_view_model.dart';

class AppMenu extends StatelessWidget {
  const AppMenu({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthViewModel>();
    return PopupMenuButton<String>(
      tooltip: 'เมนู THE_X',
      icon: const Icon(Icons.menu),
      onSelected: (value) {
        if (value == 'logout') {
          auth.logout();
        } else {
          context.go(value);
        }
      },
      itemBuilder: (_) => [
        const PopupMenuItem(value: '/profile', child: Text('โปรไฟล์')),
        const PopupMenuItem(value: '/shops', child: Text('ร้านบริการ')),
        if (!auth.isMechanic)
          const PopupMenuItem(value: '/garage', child: Text('โรงรถ')),
        PopupMenuItem(
          value: auth.isMechanic ? '/jobs' : '/bookings',
          child: Text(auth.isMechanic ? 'งานซ่อม' : 'รายการจอง'),
        ),
        if (!auth.isMechanic)
          const PopupMenuItem(value: '/ai-chat', child: Text('แชต AI')),
        const PopupMenuItem(value: '/messages', child: Text('แชตข้อความ')),
        const PopupMenuDivider(),
        const PopupMenuItem(value: 'logout', child: Text('ออกจากระบบ')),
      ],
    );
  }
}
