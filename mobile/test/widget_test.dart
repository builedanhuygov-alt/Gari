import 'package:flutter_test/flutter_test.dart';
import 'package:gari_mobile/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('GARI Mobile App smoke test & shell navigation test', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const GariMobileApp());
    await tester.pumpAndSettle();

    // Verify app bar title
    expect(find.text('GARI Leaf Intelligence'), findsOneWidget);

    // Verify navigation destinations
    expect(find.text('Chẩn Đoán'), findsOneWidget);
    expect(find.text('Trợ Lý AI'), findsOneWidget);
    expect(find.text('Vườn & Việc'), findsOneWidget);
    expect(find.text('Cộng Đồng'), findsOneWidget);
    expect(find.text('Tài Khoản'), findsOneWidget);

    // Tap on 'Trợ Lý AI' tab
    await tester.tap(find.text('Trợ Lý AI'));
    await tester.pumpAndSettle();
    expect(find.text('Trợ Lý Cây Trồng GARI'), findsOneWidget);

    // Tap on 'Vườn & Việc' tab
    await tester.tap(find.text('Vườn & Việc'));
    await tester.pumpAndSettle();
    expect(find.text('Vườn & Canh Tác'), findsOneWidget);

    // Tap on 'Cộng Đồng' tab
    await tester.tap(find.text('Cộng Đồng'));
    await tester.pumpAndSettle();
    expect(find.text('Cộng Đồng & Tri Thức'), findsOneWidget);

    // Tap on 'Tài Khoản' tab
    await tester.tap(find.text('Tài Khoản'));
    await tester.pumpAndSettle();
    expect(find.text('Tài Khoản & Cài Đặt'), findsOneWidget);
  });
}
