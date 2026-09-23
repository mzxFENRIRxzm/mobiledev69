import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:the_x/core/api/api_service.dart';
import 'package:the_x/core/auth/auth_service.dart';
import 'package:the_x/core/result.dart';
import 'package:the_x/features/profile/profile_repository.dart';
import 'package:the_x/features/profile/profile_screen.dart';
import 'package:the_x/features/profile/profile_view_model.dart';
import 'package:provider/provider.dart';
import 'package:the_x/features/auth/auth_view_model.dart';
import 'package:the_x/features/auth/auth_repository.dart';

const profile = UserProfile(
  username: 'customer',
  role: 'customer',
  firstName: 'First',
  lastName: 'Last',
  email: 'customer@example.com',
  phone: '0812345678',
);

class FakeProfiles extends ProfileRepository {
  FakeProfiles() : super(ApiService(AuthService(const FlutterSecureStorage())));
  final pending = Completer<Result<UserProfile>>();
  int saves = 0;
  @override
  Future<Result<UserProfile>> load() async => const Success(profile);
  @override
  Future<Result<UserProfile>> save(Map<String, String> values) {
    saves++;
    return pending.future;
  }
}

void main() {
  testWidgets(
    'screen feedback never recreates the edited form on save failure',
    (tester) async {
      final repository = FakeProfiles();
      final vm = ProfileViewModel(repository);
      await vm.load();
      final service = AuthService(const FlutterSecureStorage());
      final auth = AuthViewModel(AuthRepository(service, ApiService(service)))
        ..user = const AppUser('customer', 'customer')
        ..loading = false;
      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: vm),
            ChangeNotifierProvider.value(value: auth),
          ],
          child: const MaterialApp(home: ProfileScreen()),
        ),
      );
      final first = find.byType(TextFormField).first;
      await tester.ensureVisible(first);
      await tester.enterText(first, 'Unsaved edit');
      await tester.ensureVisible(find.text('บันทึกโปรไฟล์'));
      await tester.tap(find.text('บันทึกโปรไฟล์'));
      await tester.pump();
      repository.pending.complete(const Failure('บันทึกไม่สำเร็จ'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(first);
      expect(
        tester.widget<TextFormField>(first).controller!.text,
        'Unsaved edit',
      );
      expect(vm.error, 'บันทึกไม่สำเร็จ');
      await tester.pumpWidget(const SizedBox());
      vm.dispose();
      auth.dispose();
    },
  );
  test(
    'failed save preserves loaded profile; duplicate submit blocked',
    () async {
      final repository = FakeProfiles();
      final vm = ProfileViewModel(repository);
      await vm.load();
      final saving = vm.save({'phone': '0899999999'});
      expect(vm.saving, true);
      await vm.save({'phone': '0877777777'});
      expect(repository.saves, 1);
      repository.pending.complete(const Failure('บันทึกไม่สำเร็จ'));
      await saving;
      expect(vm.profile, profile);
      expect(vm.error, 'บันทึกไม่สำเร็จ');
      expect(vm.saving, false);
      vm.dispose();
    },
  );
  test(
    'navigation away during save does not notify disposed view model',
    () async {
      final repository = FakeProfiles();
      final vm = ProfileViewModel(repository);
      final saving = vm.save({'phone': '0899999999'});
      vm.dispose();
      repository.pending.complete(const Success(profile));
      await saving;
    },
  );
  testWidgets(
    'profile form validates and retains edits until successful response',
    (tester) async {
      Map<String, String>? submitted;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: ProfileForm(
                profile: profile,
                saving: false,
                onSave: (values) async {
                  submitted = values;
                },
              ),
            ),
          ),
        ),
      );
      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), ' New name ');
      await tester.enterText(fields.at(3), '123');
      await tester.ensureVisible(find.text('บันทึกโปรไฟล์'));
      await tester.tap(find.text('บันทึกโปรไฟล์'));
      await tester.pump();
      expect(submitted, null);
      expect(find.text('กรอกเบอร์โทร 9–15 หลัก'), findsOneWidget);
      await tester.enterText(fields.at(3), '+66812345678');
      await tester.ensureVisible(find.text('บันทึกโปรไฟล์'));
      await tester.tap(find.text('บันทึกโปรไฟล์'));
      await tester.pump();
      expect(submitted!['first_name'], 'New name');
      expect(submitted!['phone'], '+66812345678');
      expect(find.text(' New name '), findsOneWidget);
      expect(submitted!.containsKey('role'), false);
    },
  );
}
