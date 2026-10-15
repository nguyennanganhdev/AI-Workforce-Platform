import { CircleAlert, Loader2, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';

import { authApi } from '@/api';
import type { AreaOption, AuthUser, DomainOption } from '@/api';
import { ApiError, getBaseUrl } from '@/api/client';
import { AuthShowcase } from './AuthShowcase';
import { BRAND_NAME, BrandMark } from '@/components/layout/Brand';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from '@/components/ui/select';
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
	const [mode, setMode] = useState<Mode>('login');
	const [identity, setIdentity] = useState('');
	const [email, setEmail] = useState('');
	const [username, setUsername] = useState('');
	const [password, setPassword] = useState('');
	const [domainId, setDomainId] = useState('');
	const [areaId, setAreaId] = useState('');
	const [domains, setDomains] = useState<DomainOption[]>([]);
	const [areas, setAreas] = useState<AreaOption[]>([]);
	const [loadingDirectory, setLoadingDirectory] = useState(false);
	const [submitting, setSubmitting] = useState(false);
	const [errorMessage, setErrorMessage] = useState('');

	useEffect(() => {
		let active = true;
		setLoadingDirectory(true);
		authApi
			.listDomains()
			.then((items) => {
				if (!active) return;
				setDomains(items);
				if (items.length > 0) setDomainId((current) => current || items[0].id);
			})
			.catch(() => {
				// Login remains available even if directory loading fails.
			})
			.finally(() => {
				if (active) setLoadingDirectory(false);
			});
		return () => {
			active = false;
		};
	}, []);

	useEffect(() => {
		if (!domainId) {
			setAreas([]);
			setAreaId('');
			return;
		}
		let active = true;
		setLoadingDirectory(true);
		authApi
			.listAreas(domainId)
			.then((items) => {
				if (!active) return;
				setAreas(items);
				setAreaId(items[0]?.id ?? '');
			})
			.catch(() => {
				if (active) {
					setAreas([]);
					setAreaId('');
				}
			})
			.finally(() => {
				if (active) setLoadingDirectory(false);
			});
		return () => {
			active = false;
		};
	}, [domainId]);

	const switchMode = (next: Mode) => {
		setMode(next);
		setErrorMessage('');
	};

	const handleSubmit = async (event: React.FormEvent) => {
		event.preventDefault();
		setSubmitting(true);
		setErrorMessage('');
		try {
			const user =
				mode === 'login'
					? await authApi.login({ identity: identity.trim(), password })
					: await authApi.registerAndLogin({
							email: email.trim(),
							username: username.trim(),
							password,
							domain_id: domainId,
							area_id: areaId,
						});
			onAuthenticated(user);
		} catch (error) {
			if (error instanceof ApiError && error.status === 503) {
				setErrorMessage(t('auth.authenticationDisabled'));
			} else {
				const message = formatApiErrorForAlert(error);
				const errorKeys: Record<string, string> = {"invalid credentials":"invalidCredentials","invalid email address":"invalidEmail","username must be 3-64 lowercase letters, numbers, ., _, or -":"invalidUsername","password must be 12-1024 bytes":"invalidPassword","email or username already exists":"alreadyExists","domain_id and area_id are required":"scopeRequired","area does not belong to the selected domain":"invalidArea"};
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
									: t('auth.registerDescription')}
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

								{mode === 'register' && (
									<div className="grid gap-4 sm:grid-cols-2">
										<Field>
											<FieldLabel>{t('auth.domain')}</FieldLabel>
											<Select
												value={domainId}
												onValueChange={setDomainId}
												disabled={loadingDirectory}
											>
												<SelectTrigger className="w-full">
													<SelectValue
														placeholder={t('auth.selectDomain')}
													/>
												</SelectTrigger>
												<SelectContent>
													{domains.map((domain) => (
														<SelectItem
															key={domain.id}
															value={domain.id}
														>
															{domain.name}
														</SelectItem>
													))}
												</SelectContent>
											</Select>
										</Field>
										<Field>
											<FieldLabel>{t('auth.area')}</FieldLabel>
											<Select
												value={areaId}
												onValueChange={setAreaId}
												disabled={loadingDirectory || areas.length === 0}
											>
												<SelectTrigger className="w-full">
													<SelectValue
														placeholder={t('auth.selectArea')}
													/>
												</SelectTrigger>
												<SelectContent>
													{areas.map((area) => (
														<SelectItem key={area.id} value={area.id}>
															{area.name}
														</SelectItem>
													))}
												</SelectContent>
											</Select>
										</Field>
									</div>
								)}

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
									disabled={
										submitting ||
										(mode === 'register' && (!domainId || !areaId))
									}
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
