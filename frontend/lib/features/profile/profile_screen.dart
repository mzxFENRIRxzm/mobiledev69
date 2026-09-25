import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/config.dart';
import '../auth/auth_view_model.dart';
import '../auth/app_menu.dart';
import 'profile_repository.dart';
import 'profile_view_model.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final vm = context.watch<ProfileViewModel>();
    final auth = context.watch<AuthViewModel>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('โปรไฟล์ของฉัน'),
        leading: IconButton(
          tooltip: 'กลับหน้าหลัก',
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go(auth.isMechanic ? '/jobs' : '/garage'),
        ),
        actions: const [AppMenu()],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              // Keep the form at a stable list index when feedback changes.
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (vm.loading || vm.saving) const LinearProgressIndicator(),
                  if (vm.error != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      child: Semantics(
                        liveRegion: true,
                        child: Text(
                          vm.error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                    ),
                  if (vm.message != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      child: Semantics(
                        liveRegion: true,
                        child: Text(vm.message!),
                      ),
                    ),
                ],
              ),
              if (vm.profile != null) ...[
                const CircleAvatar(
                  radius: 36,
                  child: Icon(Icons.person_outline, size: 40),
                ),
                const SizedBox(height: 16),
                Text(
                  vm.profile!.username,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                Text(
                  vm.profile!.role == 'mechanic'
                      ? 'ผู้ให้บริการซ่อมรถจักรยานยนต์'
                      : 'สมาชิกทั่วไป',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                if (vm.profile!.pendingEmail.isNotEmpty) ...[
                  Text('อีเมลที่รอยืนยัน: ${vm.profile!.pendingEmail}'),
                  TextButton.icon(
                    onPressed: () => launchUrl(
                      Uri.parse('$apiBase/accounts/resend-verification/'),
                      webOnlyWindowName: '_blank',
                    ),
                    icon: const Icon(Icons.mark_email_unread_outlined),
                    label: const Text('ส่งลิงก์ยืนยันอีกครั้ง'),
                  ),
                  const SizedBox(height: 8),
                ],
                ProfileForm(
                  profile: vm.profile!,
                  saving: vm.saving,
                  onSave: vm.save,
                ),
                if (auth.isMechanic) ...[
                  const SizedBox(height: 24),
                  const Text(
                    'เบอร์ส่วนตัวแยกจากเบอร์ติดต่อร้าน หากต้องการแก้ข้อมูลร้าน ให้ไปที่ร้านบริการ',
                  ),
                  TextButton.icon(
                    onPressed: () => context.go('/shops'),
                    icon: const Icon(Icons.storefront),
                    label: const Text('จัดการร้านบริการ'),
                  ),
                ],
              ] else if (!vm.loading)
                OutlinedButton.icon(
                  onPressed: vm.load,
                  icon: const Icon(Icons.refresh),
                  label: const Text('ลองโหลดโปรไฟล์อีกครั้ง'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class ProfileForm extends StatefulWidget {
  final UserProfile profile;
  final bool saving;
  final Future<void> Function(Map<String, String>) onSave;
  const ProfileForm({
    super.key,
    required this.profile,
    required this.saving,
    required this.onSave,
  });
  @override
  State<ProfileForm> createState() => _ProfileFormState();
}

class _ProfileFormState extends State<ProfileForm> {
  final form = GlobalKey<FormState>();
  final first = TextEditingController(),
      last = TextEditingController(),
      email = TextEditingController(),
      phone = TextEditingController();
  void populate() {
    first.text = widget.profile.firstName;
    last.text = widget.profile.lastName;
    email.text = widget.profile.pendingEmail.isNotEmpty
        ? widget.profile.pendingEmail
        : widget.profile.email;
    phone.text = widget.profile.phone;
  }

  @override
  void initState() {
    super.initState();
    populate();
  }

  @override
  void didUpdateWidget(covariant ProfileForm oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.profile != widget.profile) populate();
  }

  @override
  void dispose() {
    first.dispose();
    last.dispose();
    email.dispose();
    phone.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Form(
    key: form,
    child: Column(
      children: [
        TextFormField(
          controller: first,
          enabled: !widget.saving,
          maxLength: 150,
          textInputAction: TextInputAction.next,
          autofillHints: const [AutofillHints.givenName],
          decoration: const InputDecoration(labelText: 'ชื่อ'),
        ),
        const SizedBox(height: 16),
        TextFormField(
          controller: last,
          enabled: !widget.saving,
          maxLength: 150,
          textInputAction: TextInputAction.next,
          autofillHints: const [AutofillHints.familyName],
          decoration: const InputDecoration(labelText: 'นามสกุล'),
        ),
        const SizedBox(height: 16),
        TextFormField(
          controller: email,
          enabled: !widget.saving,
          maxLength: 254,
          keyboardType: TextInputType.emailAddress,
          autofillHints: const [AutofillHints.email],
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(labelText: 'อีเมล (ไม่บังคับ)'),
          validator: (value) =>
              (value?.trim().isEmpty ?? true) || RegExp(
                r'^[^\s@]+@[^\s@]+\.[^\s@]+$',
              ).hasMatch(value?.trim() ?? '')
              ? null
              : 'กรุณากรอกอีเมลให้ถูกต้อง',
        ),
        const SizedBox(height: 16),
        TextFormField(
          controller: phone,
          enabled: !widget.saving,
          maxLength: 16,
          keyboardType: TextInputType.phone,
          autofillHints: const [AutofillHints.telephoneNumber],
          decoration: const InputDecoration(
            labelText: 'เบอร์โทรศัพท์',
            hintText: '0812345678 หรือ +66812345678',
          ),
          validator: (value) =>
              RegExp(r'^\+?[0-9]{9,15}$').hasMatch(value?.trim() ?? '')
              ? null
              : 'กรอกเบอร์โทร 9–15 หลัก',
        ),
        const SizedBox(height: 24),
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: widget.saving
                ? null
                : () {
                    if (form.currentState!.validate()) {
                      widget.onSave({
                        'first_name': first.text.trim(),
                        'last_name': last.text.trim(),
                        'email': email.text.trim(),
                        'phone': phone.text.trim(),
                      });
                    }
                  },
            icon: const Icon(Icons.save_outlined),
            label: Text(widget.saving ? 'กำลังบันทึก…' : 'บันทึกโปรไฟล์'),
          ),
        ),
      ],
    ),
  );
}
