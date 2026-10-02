import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'auth_view_model.dart';
import '../../core/ui/app_theme.dart';
import '../../core/ui/app_widgets.dart';

class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthViewModel>();
    return Scaffold(
      appBar: AppBar(
        title: const BrandMark(),
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 24),
            child: Center(
              child: Text(
                'YOUR RIDE, CARED FOR',
                style: TextStyle(
                  fontSize: 10,
                  color: AppColors.muted,
                  letterSpacing: 1.4,
                ),
              ),
            ),
          ),
        ],
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1120),
            child: LayoutBuilder(
              builder: (context, size) {
                final welcome = Reveal(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'THE_X  /  MOTORCYCLE CARE',
                        style: TextStyle(
                          fontSize: 12,
                          color: AppColors.gold,
                          letterSpacing: 2,
                        ),
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'ดูแลรถคู่ใจ\nให้พร้อมทุกเส้นทาง',
                        style: Theme.of(context).textTheme.headlineLarge,
                      ),
                      const SizedBox(height: 18),
                      const Text(
                        'พื้นที่เดียวสำหรับรถของคุณและร้านที่ไว้ใจ\nตั้งแต่ดูแลประจำวัน จนถึงวันที่ต้องเข้ารับบริการ',
                        style: TextStyle(color: AppColors.muted, height: 1.8),
                      ),
                      const SizedBox(height: 32),
                      const Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: [
                          _FeatureLabel(Icons.two_wheeler, 'โรงรถส่วนตัว'),
                          _FeatureLabel(
                            Icons.event_available_outlined,
                            'จองและติดตามงาน',
                          ),
                          _FeatureLabel(
                            Icons.auto_awesome_outlined,
                            'ผู้ช่วย AI',
                          ),
                        ],
                      ),
                    ],
                  ),
                );
                final login = Reveal(
                  delay: 100,
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(28),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Align(
                            alignment: Alignment.centerLeft,
                            child: Container(
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: AppColors.gold.withValues(alpha: .08),
                                borderRadius: BorderRadius.circular(16),
                              ),
                              child: const Icon(
                                Icons.key_outlined,
                                color: AppColors.gold,
                                size: 28,
                              ),
                            ),
                          ),
                          const SizedBox(height: 24),
                          Text(
                            'ยินดีต้อนรับกลับ',
                            style: Theme.of(context).textTheme.headlineMedium,
                          ),
                          const SizedBox(height: 10),
                          const Text(
                            'เข้าสู่บัญชีเพื่อเปิดโรงรถและจัดการนัดหมายของคุณ',
                            style: TextStyle(
                              color: AppColors.muted,
                              height: 1.7,
                            ),
                          ),
                          const SizedBox(height: 28),
                          if (auth.error != null)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 18),
                              child: Text(
                                auth.error!,
                                style: TextStyle(
                                  color: Theme.of(context).colorScheme.error,
                                ),
                              ),
                            ),
                          FilledButton.icon(
                            onPressed: auth.loading ? null : auth.login,
                            icon: const Icon(Icons.arrow_forward_rounded),
                            label: const Text('เข้าสู่ระบบ THE_X'),
                          ),
                          const SizedBox(height: 22),
                          const Text(
                            'กรอกชื่อผู้ใช้และรหัสผ่านในหน้าถัดไป\nหากยังไม่มีบัญชี เลือกสมัครสมาชิกได้ในหน้านั้น',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: AppColors.muted,
                              fontSize: 12,
                              height: 1.8,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
                return Column(
                  children: [
                    if (size.maxWidth >= 900 &&
                        MediaQuery.textScalerOf(context).scale(14) <= 20)
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          Expanded(flex: 6, child: welcome),
                          const SizedBox(width: 70),
                          Expanded(flex: 5, child: login),
                        ],
                      )
                    else ...[
                      welcome,
                      const SizedBox(height: 32),
                      login,
                    ],
                    const SizedBox(height: 44),
                    const Text(
                      'THE_X · ดูแลรถและทุกการเดินทางของคุณ',
                      style: TextStyle(fontSize: 11, color: AppColors.muted),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _FeatureLabel extends StatelessWidget {
  final IconData icon;
  final String text;
  const _FeatureLabel(this.icon, this.text);
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: 18, color: AppColors.gold),
      const SizedBox(width: 8),
      Text(text, style: const TextStyle(fontSize: 12, color: AppColors.muted)),
    ],
  );
}
