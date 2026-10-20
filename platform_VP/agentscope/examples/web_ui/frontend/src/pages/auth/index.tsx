import { CircleAlert, Loader2, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';

import { AuthShowcase } from './AuthShowcase';
import { authApi } from '@/api';
import type { AreaOption, AuthUser, DomainOption } from '@/api';
import { ApiError } from '@/api/client';
import heroSquad from '@/assets/images/brand/hero-squad-768.webp';
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
import './auth-page.css';

interface Props {
	onAuthenticated: (user: AuthUser) => void;
}

type Mode = 'login' | 'register';

export function AuthPage({ onAuthenticated }: Props) {
	useCueTheme();
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
			} else if (mode === 'login' && error instanceof ApiError && error.status === 401) {
				setErrorMessage(t('auth.errors.invalidCredentials'));
			} else {
				setErrorMessage(formatApiErrorForAlert(error));
			}
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<div className="vg-auth relative flex min-h-screen flex-col overflow-hidden bg-background">
			{/* Warm studio light behind the page, as on the landing hero. */}
			<div aria-hidden className="vg-auth-glow pointer-events-none absolute inset-0" />

			<header className="relative mx-auto flex w-full max-w-6xl items-center px-5 py-5 sm:px-8">
				<div className="flex items-center gap-2.5">
					<BrandMark className="size-9" />
					<span className="text-xl font-semibold tracking-tight">{BRAND_NAME}</span>
				</div>
			</header>

			<main className="relative mx-auto grid w-full max-w-6xl flex-1 items-center gap-10 px-5 pb-12 sm:px-8 lg:grid-cols-[1fr_420px] lg:gap-16">
				<section className="hidden lg:block">
					<span className="vg-auth-chip inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium">
						<span className="size-1.5 rounded-full bg-[var(--vg-accent)]" />
						{t('auth.brand')}
					</span>
					<h1 className="mt-5 max-w-xl text-[44px]/[1.1] font-black tracking-[-0.045em]">
						{t('auth.heroTitle')}
					</h1>
					<span
						aria-hidden
						className="mt-5 block h-1 w-16 rounded-full bg-[linear-gradient(90deg,var(--vg-accent),var(--vg-accent-bright))]"
					/>
					<p className="mt-5 max-w-lg text-base/7 text-muted-foreground">
						{t('auth.heroDescription')}
					</p>
					{/* What the platform does, played out by its own agents. */}
					<div className="mt-7">
						<AuthShowcase />
					</div>
					<div className="mt-5 flex items-center gap-2 text-sm text-muted-foreground">
						<ShieldCheck className="size-4 text-[var(--cue-success,currentColor)]" />
						{t('auth.securityHint')}
					</div>
				</section>

				<Card className="vg-auth-card gap-0 overflow-hidden rounded-[28px] bg-background p-2 pt-0 ring-0">
					<div className="-mx-2 flex justify-center bg-[linear-gradient(180deg,var(--vg-accent-soft),transparent)] px-6 pt-4">
						<img
							src={heroSquad}
							alt=""
							width={768}
							height={768}
							className="vg-auth-squad h-40 w-auto object-contain object-bottom"
						/>
					</div>
					<CardHeader className="space-y-4 pt-2">
						<div>
							<CardTitle className="text-[22px]/7 font-bold tracking-[-0.02em]">
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
								variant="ghost"
								size="sm"
								data-active={mode === 'login'}
								className="vg-auth-tab rounded-full font-semibold hover:bg-transparent"
								onClick={() => switchMode('login')}
							>
								{t('auth.login')}
							</Button>
							<Button
								type="button"
								variant="ghost"
								size="sm"
								data-active={mode === 'register'}
								className="vg-auth-tab rounded-full font-semibold hover:bg-transparent"
								onClick={() => switchMode('register')}
							>
								{t('auth.register')}
							</Button>
						</div>
					</CardHeader>

					<CardContent className="pt-5 pb-4">
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
											<FieldDescription>
												{t('auth.usernameHint')}
											</FieldDescription>
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
									className="vg-auth-cta h-11 w-full rounded-full text-[15px] font-semibold"
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
