import { CircleAlert, Loader2, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';

import { AuthShowcase } from './AuthShowcase';
import { authApi } from '@/api';
import type { AreaOption, AuthUser, DomainOption } from '@/api';
import { ApiError } from '@/api/client';
import { Brand } from '@/components/layout/Brand';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';

interface Props {
	onAuthenticated: (user: AuthUser) => void;
}

type Mode = 'login' | 'register';

const controlClassName = 'h-11 border-border bg-background text-foreground shadow-none';

export function AuthPage({ onAuthenticated }: Props) {
	const { t } = useTranslation();
	const [mode, setMode] = useState<Mode>(() =>
		window.location.pathname === '/register' ? 'register' : 'login',
	);
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
				setErrorMessage(formatApiErrorForAlert(error));
			}
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<div className="vagents-auth">
			<header className="vagents-auth-header">
				<a href="/" aria-label="VAgents - Trang chủ">
					<Brand />
				</a>
				<span className="flex items-center gap-2 text-xs text-muted-foreground">
					<ShieldCheck className="size-4 text-[#b64e0b]" />
					{t('auth.secureAccess')}
				</span>
			</header>
			<main className="vagents-auth-layout">
				<section className="vagents-auth-copy" aria-labelledby="auth-hero-title">
					<div className="vagents-auth-eyebrow">VAgents · AI Workforce</div>
					<h1 id="auth-hero-title">{t('auth.heroTitle')}</h1>
					<p>{t('auth.heroDescription')}</p>
					<AuthShowcase />
					<div className="mt-6 flex items-start gap-2 text-xs leading-5 text-muted-foreground">
						<ShieldCheck className="mt-0.5 size-4 shrink-0" />
						{t('auth.securityHint')}
					</div>
				</section>
				<Card className="vagents-auth-panel">
					<CardHeader className="space-y-5 p-6">
						<div>
							<CardTitle className="text-xl font-semibold tracking-tight">
								{mode === 'login' ? t('auth.loginTitle') : t('auth.registerTitle')}
							</CardTitle>
							<CardDescription className="mt-2 leading-6">
								{mode === 'login'
									? t('auth.loginDescription')
									: t('auth.registerDescription')}
							</CardDescription>
						</div>
						<div className="vagents-auth-tabs">
							<Button
								type="button"
								variant="ghost"
								aria-pressed={mode === 'login'}
								onClick={() => switchMode('login')}
							>
								{t('auth.login')}
							</Button>
							<Button
								type="button"
								variant="ghost"
								aria-pressed={mode === 'register'}
								onClick={() => switchMode('register')}
							>
								{t('auth.register')}
							</Button>
						</div>
					</CardHeader>
					<CardContent className="px-6 pb-6">
						<form onSubmit={handleSubmit}>
							<FieldGroup>
								{mode === 'login' ? (
									<Field>
										<FieldLabel htmlFor="identity" className="text-foreground">
											{t('auth.identity')}
										</FieldLabel>
										<Input
											id="identity"
											autoComplete="username"
											className={controlClassName}
											value={identity}
											onChange={(event) => setIdentity(event.target.value)}
											required
										/>
									</Field>
								) : (
									<>
										<Field>
											<FieldLabel htmlFor="email" className="text-foreground">
												{t('auth.email')}
											</FieldLabel>
											<Input
												id="email"
												type="email"
												autoComplete="email"
												className={controlClassName}
												value={email}
												onChange={(event) => setEmail(event.target.value)}
												required
											/>
										</Field>
										<Field>
											<FieldLabel
												htmlFor="username"
												className="text-foreground"
											>
												{t('auth.username')}
											</FieldLabel>
											<Input
												id="username"
												autoComplete="username"
												minLength={3}
												className={controlClassName}
												value={username}
												onChange={(event) =>
													setUsername(event.target.value)
												}
												required
											/>
										</Field>
									</>
								)}

								<Field>
									<FieldLabel htmlFor="password" className="text-foreground">
										{t('auth.password')}
									</FieldLabel>
									<Input
										id="password"
										type="password"
										autoComplete={
											mode === 'login' ? 'current-password' : 'new-password'
										}
										minLength={mode === 'register' ? 12 : 1}
										className={controlClassName}
										value={password}
										onChange={(event) => setPassword(event.target.value)}
										required
									/>
									{mode === 'register' && (
										<FieldDescription className="text-muted-foreground">
											{t('auth.passwordHint')}
										</FieldDescription>
									)}
								</Field>

								{mode === 'register' && (
									<div className="grid gap-4 sm:grid-cols-2">
										<Field>
											<FieldLabel htmlFor="auth-domain">
												{t('auth.domain')}
											</FieldLabel>
											<select
												id="auth-domain"
												className={`${controlClassName} w-full min-w-0 rounded-lg border px-3 text-sm`}
												value={domainId}
												onChange={(event) =>
													setDomainId(event.target.value)
												}
												disabled={loadingDirectory}
											>
												<option value="" disabled>
													{t('auth.selectDomain')}
												</option>
												{domains.map((domain) => (
													<option key={domain.id} value={domain.id}>
														{domain.name}
													</option>
												))}
											</select>
										</Field>
										<Field>
											<FieldLabel htmlFor="auth-area">
												{t('auth.area')}
											</FieldLabel>
											<select
												id="auth-area"
												className={`${controlClassName} w-full min-w-0 rounded-lg border px-3 text-sm`}
												value={areaId}
												onChange={(event) => setAreaId(event.target.value)}
												disabled={loadingDirectory || areas.length === 0}
											>
												<option value="" disabled>
													{t('auth.selectArea')}
												</option>
												{areas.map((area) => (
													<option key={area.id} value={area.id}>
														{area.name}
													</option>
												))}
											</select>
										</Field>
									</div>
								)}

								{errorMessage && (
									<Alert
										variant="destructive"
										className="border-destructive/25 bg-destructive/5 text-destructive"
									>
										<CircleAlert />
										<AlertDescription>{errorMessage}</AlertDescription>
									</Alert>
								)}

								<Button
									type="submit"
									className="vagents-auth-submit h-11 w-full font-semibold"
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
					</CardContent>
				</Card>
			</main>
		</div>
	);
}
