import { test, expect } from '@playwright/test';

test('create and publish agent, real session flow, context, knowledge and mobile navigation', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await page.getByLabel('Email').fill('browser@test.local');
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Ui-acceptance-only-123!');
  await page.getByRole('button', { name: 'Vào workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Không gian làm việc' })).toBeVisible();
  await page.getByRole('link', { name: 'Model & provider', exact: true }).click();
  await page.getByRole('button', { name: 'Thêm model & provider' }).click();
  await page.getByLabel('Tên', { exact: true }).fill('Acceptance provider · fixture I/O');
  await page.getByLabel('Adapter', { exact: true }).selectOption('ollama');
  await page.getByLabel('Model ID').fill('fixture');
  await page.getByLabel('Nguồn / phiên bản giá').fill('fixture-no-real-billing');
  await page.getByLabel('Context tối đa').fill('128000');
  await page.getByRole('button', { name: 'Lưu', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('link', { name: 'Đội ngũ agent', exact: true }).click();
  await page.getByRole('button', { name: 'Tạo agent', exact: true }).click();
  await page.getByLabel('Tên agent').fill('Chuyên viên xác minh');
  await page
    .getByLabel('Mục đích / công việc chịu trách nhiệm')
    .fill('Kiểm chứng các dữ kiện với tài liệu có nguồn.');
  await page
    .getByLabel('Danh tính và nguyên tắc làm việc')
    .fill('Tôi là chuyên viên xác minh, hỏi lại khi thiếu bằng chứng.');
  await page
    .getByLabel('Model chính', { exact: true })
    .selectOption({ label: 'Acceptance provider · fixture I/O' });
  await page.getByLabel('Chọn model', { exact: true }).selectOption('manual');
  await page.getByLabel('Bộ nhớ', { exact: true }).selectOption('verified_private');
  await page.getByRole('button', { name: 'Lưu', exact: true }).click();
  await page.getByRole('button', { name: /01.*Chuyên viên xác minh/ }).click();
  await page.getByRole('button', { name: 'Kiểm tra chính sách' }).click();
  await expect(page.getByText(/Policy test: đạt/)).toBeVisible();
  await page.getByRole('button', { name: 'Công bố', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Chọn làm bản hiện hành' })).toBeVisible();
  await page.getByRole('button', { name: 'Đóng', exact: true }).click();
  await page.getByRole('link', { name: 'Sessions', exact: true }).click();
  await page.getByRole('button', { name: 'Session mới' }).click();
  await page.getByLabel('Tên công việc').fill('Kiểm tra thiếu dữ liệu');
  await page.getByLabel('Team ·').selectOption({ label: 'Chuyên viên xác minh' });
  await page.getByRole('button', { name: 'Lưu', exact: true }).click();
  await page
    .getByLabel('Mục tiêu / thông tin bổ sung')
    .fill('Hãy kiểm chứng thông tin; tôi chưa có tài liệu.');
  await page.getByRole('button', { name: 'Gửi việc' }).click();
  await expect(page.getByText('Cần tài liệu có nguồn để kiểm chứng.')).toBeVisible({
    timeout: 20000,
  });
  await page.getByRole('tab', { name: 'Context', exact: true }).click();
  await expect(page.getByText(/kết quả được chấp nhận/)).toBeVisible();
  await page.getByText('Xem context được chọn').click();
  await expect(page.locator('.inspector pre')).toContainText('Hãy kiểm chứng thông tin');
  await page.screenshot({
    path: 'test-results/session-desktop.png',
    fullPage: true,
    animations: 'disabled',
  });
  await page.getByRole('link', { name: 'Tri thức', exact: true }).click();
  await page.getByRole('button', { name: 'Thêm kho tri thức' }).click();
  await page.getByLabel('Tên', { exact: true }).fill('Chính sách thử nghiệm');
  await page.getByLabel('Phạm vi').selectOption('workspace');
  await page.getByRole('button', { name: 'Lưu', exact: true }).click();
  await page.getByRole('button', { name: 'Tài liệu & tra cứu' }).click();
  await page.locator('input[type=file]').setInputFiles({
    name: 'policy.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Chi phí hợp lệ là 100 đồng.', 'utf8'),
  });
  await expect(page.getByText('ready · 1 đoạn')).toBeVisible({ timeout: 15000 });
  await page.getByLabel('Tra cứu nguồn').fill('chi phí');
  await page.getByRole('button', { name: 'Tìm', exact: true }).click();
  await expect(page.getByText('Chi phí hợp lệ là 100 đồng.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Đóng', exact: true }).click();
  await page.setViewportSize({ width: 375, height: 812 });
  await page.getByRole('button', { name: 'Mở điều hướng' }).click();
  await page.getByRole('link', { name: 'Đội ngũ agent', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Đội ngũ agent' })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
  ).toBeTruthy();
  await page.screenshot({
    path: 'test-results/agents-mobile.png',
    fullPage: true,
    animations: 'disabled',
  });
  expect(errors).toEqual([]);
});
