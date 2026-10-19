import { CircleAlert, Loader2, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

import { AuthShowcase } from './AuthShowcase';
import { authApi } from '@/api';
import type { AuthUser } from '@/api';
import { ApiError, getBaseUrl } from '@/api/client';
import { BRAND_NAME, BrandMark } from '@/components/layout/Brand';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { useCueTheme } from '@/hooks/useCueTheme';
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';

interface Props {
	onAuthenticated: (user: AuthUser) => void;
}

type Mode = 'login' | 'register';

export function AuthPage({ onAuthenticated }: Props) {
	useCueTheme();
	const { t } = useTranslation();
	const [mode, setMode] = useState<Mode>(() => window.location.pathname === '/register' ? 'register' : 'login');
	const [identity, setIdentity] = useState('');
	const [email, setEmail] = useState('');
	const [username, setUsername] = useState('');
	const [password, setPassword] = useState('');
	const [submitting, setSubmitting] = useState(false);
	const [errorMessage, setErrorMessage] = useState('');

	const switchMode = (next: Mode) => {
		setMode(next);
		setErrorMessage('');
	};

	const handleSubmit = async (event: React.FormEvent) => {
		event.preventDefault();
		setSubmitting(true);
		setErrorMessage('');
		try {
			if (mode !== 'login') {
				// Everyone signs up as a personal account; staff accounts are made by an admin.
				const registered = await authApi.registerPersonal({ email: email.trim(), username: username.trim(), password });
				if (registered.status === 'pending') {
					setMode('login');
					setIdentity(username.trim());
					setPassword('');
					setErrorMessage('Đã gửi đăng ký. Tài khoản đang chờ quản trị duyệt.');
					return;
				}
			}
			const user = await authApi.login({
				identity: mode === 'login' ? identity.trim() : username.trim(),
				password,
			});
			onAuthenticated(user);
		} catch (error) {
			if (error instanceof ApiError && error.status === 403) {
				setErrorMessage('Tài khoản đang chờ quản trị duyệt. Vui lòng thử lại sau khi được duyệt.');
			} else if (error instanceof ApiError && error.status === 409 && mode !== 'login') {
				setErrorMessage('Email hoặc tên đăng nhập đã được sử dụng.');
			} else if (error instanceof ApiError && error.status === 503) {
				setErrorMessage(t('auth.authenticationDisabled'));
			} else {
				const message = formatApiErrorForAlert(error);
				const errorKeys: Record<string, string> = {"invalid credentials":"invalidCredentials","invalid email address":"invalidEmail","username must be 3-64 lowercase letters, numbers, ., _, or -":"invalidUsername","password must be 12-1024 bytes":"invalidPassword","email or username already exists":"alreadyExists"};
				const key = errorKeys[message];
				setErrorMessage(key ? t('auth.errors.' + key) : message);
			}
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-canvas px-4 py-10">
			<div className="relative grid w-full max-w-5xl gap-8 lg:grid-cols-[1fr_400px] lg:items-center lg:gap-14">
				<div className="hidden space-y-6 lg:block">
					<div className="flex items-center gap-3">
						<BrandMark className="size-10" />
						<p className="text-[15px]/5 font-semibold">{t('auth.brand')}</p>
					</div>
					<div className="space-y-2">
						<h1 className="max-w-xl text-[30px]/[38px] font-semibold tracking-tight">
							{t('auth.heroTitle')}
						</h1>
						<p className="max-w-lg text-[15px]/[22px] text-muted-foreground">
							{t('auth.heroDescription')}
						</p>
					</div>
					{/* What the platform does, played out by its own agents. */}
					<AuthShowcase />
					<div className="flex items-center gap-2 text-sm text-muted-foreground">
						<ShieldCheck className="size-4 text-[var(--cue-success,currentColor)]" />
						{t('auth.securityHint')}
					</div>
				</div>

				<Card className="rounded-3xl border border-[var(--cue-border,var(--border))] bg-background p-2 shadow-[var(--cue-shadow-float,none)] ring-0">
					<CardHeader className="space-y-4">
						<div className="flex items-center gap-3 lg:hidden">
							<BrandMark className="size-9" />
							<span className="font-semibold">{BRAND_NAME}</span>
						</div>
						<div>
							<CardTitle className="text-[17px]/6 font-semibold">
								{mode === 'login' ? t('auth.loginTitle') : t('auth.registerTitle')}
							</CardTitle>
							<CardDescription className="mt-1.5">
								{mode === 'login'
									? t('auth.loginDescription')
									: 'Tạo tài khoản để dựng đội agent của riêng bạn. Gói như Vinhomes hay Travelling được thêm sau khi đăng nhập.'}
							</CardDescription>
						</div>
						<div className="grid grid-cols-2 rounded-full bg-[var(--cue-bg-subtle,var(--muted))] p-1">
							<Button
								type="button"
								variant={mode === 'login' ? 'outline' : 'ghost'}
								size="sm"
								className="rounded-full border-transparent data-[variant=outline]:shadow-[0_1px_2px_rgba(0,0,0,.06)]"
								onClick={() => switchMode('login')}
							>
								{t('auth.login')}
							</Button>
							<Button
								type="button"
								variant={mode === 'register' ? 'outline' : 'ghost'}
								size="sm"
								className="rounded-full border-transparent data-[variant=outline]:shadow-[0_1px_2px_rgba(0,0,0,.06)]"
								onClick={() => switchMode('register')}
							>
								{t('auth.register')}
							</Button>
						</div>
					</CardHeader>

					<CardContent>
						<form onSubmit={handleSubmit}>
							<FieldGroup>
								{mode === 'login' ? (
									<Field>
										<FieldLabel htmlFor="identity">
											{t('auth.identity')}
										</FieldLabel>
										<Input
											id="identity"
											autoComplete="username"
											value={identity}
											onChange={(event) => setIdentity(event.target.value)}
											required
										/>
									</Field>
								) : (
									<>
										<Field>
											<FieldLabel htmlFor="email">
												{t('auth.email')}
											</FieldLabel>
											<Input
												id="email"
												type="email"
												autoComplete="email"
												value={email}
												onChange={(event) => setEmail(event.target.value)}
												required
											/>
										</Field>
										<Field>
											<FieldLabel htmlFor="username">
												{t('auth.username')}
											</FieldLabel>
											<Input
												id="username"
												autoComplete="username"
												minLength={3}
												value={username}
												onChange={(event) =>
													setUsername(event.target.value)
												}
												required
											/>
										<FieldDescription>{t('auth.usernameHint')}</FieldDescription>
										</Field>
									</>
								)}

								<Field>
									<FieldLabel htmlFor="password">{t('auth.password')}</FieldLabel>
									<Input
										id="password"
										type="password"
										autoComplete={
											mode === 'login' ? 'current-password' : 'new-password'
										}
										minLength={mode === 'register' ? 12 : 1}
										value={password}
										onChange={(event) => setPassword(event.target.value)}
										required
									/>
									{mode === 'register' && (
										<FieldDescription>
											{t('auth.passwordHint')}
										</FieldDescription>
									)}
								</Field>

								{errorMessage && (
									<Alert variant="destructive">
										<CircleAlert />
										<AlertDescription>{errorMessage}</AlertDescription>
									</Alert>
								)}

								<Button
									type="submit"
									size="lg"
									className="w-full"
									disabled={submitting}
								>
									{submitting && <Loader2 className="size-4 animate-spin" />}
									{mode === 'login' ? t('auth.login') : t('auth.createAccount')}
								</Button>
							</FieldGroup>
						</form>
						<p className="mt-5 text-center text-xs text-muted-foreground">
							{t('auth.connectedTo')} {getBaseUrl()}
						</p>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
