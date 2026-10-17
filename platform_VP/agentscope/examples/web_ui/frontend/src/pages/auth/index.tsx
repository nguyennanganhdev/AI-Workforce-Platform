import { CircleAlert, Loader2, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';

import { authApi } from '@/api';
import type { AreaOption, AuthUser, DomainOption } from '@/api';
import { ApiError, getBaseUrl } from '@/api/client';
import AgentScope from '@/assets/images/agentscope_mono.svg?react';
import heroBackground from '@/assets/images/workforce-auth-hero.jpg';
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
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';

interface Props {
	onAuthenticated: (user: AuthUser) => void;
}

type Mode = 'login' | 'register';

const controlClassName =
	'h-11 border-white/15 bg-white/[0.07] text-white shadow-none placeholder:text-white/35 focus-visible:border-[#ffad6a] focus-visible:ring-[#ffad6a]/25';

export function AuthPage({ onAuthenticated }: Props) {
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
				setErrorMessage(formatApiErrorForAlert(error));
			}
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<div className="dark relative min-h-[100dvh] overflow-hidden bg-[#040814] text-white">
			<div className="pointer-events-none fixed inset-0" aria-hidden="true">
				<img
					src={heroBackground}
					alt=""
					fetchPriority="high"
					decoding="async"
					className="auth-backdrop h-full w-full object-cover object-center"
				/>
				<div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(3,7,18,0.96)_0%,rgba(3,7,18,0.74)_38%,rgba(3,7,18,0.34)_64%,rgba(3,7,18,0.86)_100%)]" />
				<div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(3,7,18,0.18)_0%,rgba(3,7,18,0.84)_100%)]" />
			</div>

			<header className="relative z-20 mx-auto flex h-[76px] w-full max-w-[1440px] items-center justify-between px-5 sm:px-8 lg:px-12">
				<div className="flex items-center gap-3">
					<div className="flex size-10 items-center justify-center rounded-xl border border-white/15 bg-white/10 text-white shadow-[0_10px_30px_rgba(0,0,0,0.25)] backdrop-blur-md">
						<AgentScope className="size-6" />
					</div>
					<div>
						<p className="text-sm font-semibold tracking-[0.02em]">AI Workforce</p>
						<p className="text-[11px] text-white/50">AgentScope Platform</p>
					</div>
				</div>
				<div className="hidden items-center gap-2 text-xs text-white/60 sm:flex">
					<ShieldCheck className="size-4 text-[#ffad6a]" />
					{t('auth.secureAccess')}
				</div>
			</header>

			<main className="relative z-10 mx-auto grid min-h-[calc(100dvh-76px)] w-full max-w-[1440px] items-center gap-10 px-5 pb-12 pt-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_440px] lg:gap-16 lg:px-12 lg:pb-20 lg:pt-8 xl:grid-cols-[minmax(0,1fr)_460px] xl:gap-24">
				<section className="auth-copy max-w-2xl pt-4 lg:pt-0" aria-labelledby="auth-hero-title">
					<p className="mb-5 text-xs font-semibold uppercase tracking-[0.24em] text-[#ffbc87] sm:text-sm">
						{t('auth.eyebrow')}
					</p>
					<h1
						id="auth-hero-title"
						className="max-w-[760px] text-[clamp(2.65rem,6vw,5.6rem)] font-semibold leading-[0.94] tracking-[-0.055em] text-white [text-wrap:balance]"
					>
						{t('auth.heroTitle')}
					</h1>
					<p className="mt-6 max-w-xl text-base leading-7 text-white/68 sm:text-lg sm:leading-8">
						{t('auth.heroDescription')}
					</p>
					<div className="mt-7 flex max-w-xl items-start gap-3 border-l-2 border-[#ffad6a]/70 pl-4 text-sm leading-6 text-white/58">
						<ShieldCheck className="mt-1 size-4 shrink-0 text-[#ffad6a]" />
						<span>{t('auth.securityHint')}</span>
					</div>
				</section>

				<Card className="auth-panel w-full border-white/15 bg-[#091226]/90 py-0 text-white shadow-[0_32px_90px_rgba(0,0,0,0.5)] backdrop-blur-2xl">
					<CardHeader className="space-y-5 border-b border-white/10 px-5 pb-5 pt-6 sm:px-7 sm:pt-7">
						<div>
							<CardTitle className="text-2xl font-semibold tracking-[-0.025em] text-white">
								{mode === 'login' ? t('auth.loginTitle') : t('auth.registerTitle')}
							</CardTitle>
							<CardDescription className="mt-2 leading-6 text-white/52">
								{mode === 'login'
									? t('auth.loginDescription')
									: t('auth.registerDescription')}
							</CardDescription>
						</div>
						<div className="grid grid-cols-2 rounded-xl border border-white/10 bg-black/20 p-1">
							<Button
								type="button"
								variant="ghost"
								size="sm"
								aria-pressed={mode === 'login'}
								className={
									mode === 'login'
										? 'bg-white/12 text-white hover:bg-white/16 hover:text-white'
										: 'text-white/48 hover:bg-white/5 hover:text-white'
								}
								onClick={() => switchMode('login')}
							>
								{t('auth.login')}
							</Button>
							<Button
								type="button"
								variant="ghost"
								size="sm"
								aria-pressed={mode === 'register'}
								className={
									mode === 'register'
										? 'bg-white/12 text-white hover:bg-white/16 hover:text-white'
										: 'text-white/48 hover:bg-white/5 hover:text-white'
								}
								onClick={() => switchMode('register')}
							>
								{t('auth.register')}
							</Button>
						</div>
					</CardHeader>

					<CardContent className="px-5 pb-6 pt-5 sm:px-7 sm:pb-7">
						<form onSubmit={handleSubmit}>
							<FieldGroup>
								{mode === 'login' ? (
									<Field>
										<FieldLabel htmlFor="identity" className="text-white/78">
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
											<FieldLabel htmlFor="email" className="text-white/78">
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
											<FieldLabel htmlFor="username" className="text-white/78">
												{t('auth.username')}
											</FieldLabel>
											<Input
												id="username"
												autoComplete="username"
												minLength={3}
												className={controlClassName}
												value={username}
												onChange={(event) => setUsername(event.target.value)}
												required
											/>
										</Field>
									</>
								)}

								<Field>
									<FieldLabel htmlFor="password" className="text-white/78">
										{t('auth.password')}
									</FieldLabel>
									<Input
										id="password"
										type="password"
										autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
										minLength={mode === 'register' ? 12 : 1}
										className={controlClassName}
										value={password}
										onChange={(event) => setPassword(event.target.value)}
										required
									/>
									{mode === 'register' && (
										<FieldDescription className="text-white/42">
											{t('auth.passwordHint')}
										</FieldDescription>
									)}
								</Field>

								{mode === 'register' && (
									<div className="grid gap-4 sm:grid-cols-2">
										<Field>
											<FieldLabel className="text-white/78">{t('auth.domain')}</FieldLabel>
											<Select
												value={domainId}
												onValueChange={setDomainId}
												disabled={loadingDirectory}
											>
												<SelectTrigger className={`${controlClassName} w-full`}>
													<SelectValue placeholder={t('auth.selectDomain')} />
												</SelectTrigger>
												<SelectContent className="border-white/15 bg-[#0c1730] text-white">
													{domains.map((domain) => (
														<SelectItem key={domain.id} value={domain.id}>
															{domain.name}
														</SelectItem>
													))}
												</SelectContent>
											</Select>
										</Field>
										<Field>
											<FieldLabel className="text-white/78">{t('auth.area')}</FieldLabel>
											<Select
												value={areaId}
												onValueChange={setAreaId}
												disabled={loadingDirectory || areas.length === 0}
											>
												<SelectTrigger className={`${controlClassName} w-full`}>
													<SelectValue placeholder={t('auth.selectArea')} />
												</SelectTrigger>
												<SelectContent className="border-white/15 bg-[#0c1730] text-white">
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
									<Alert
										variant="destructive"
										className="border-red-300/25 bg-red-500/10 text-red-100 [&>svg]:text-red-300"
									>
										<CircleAlert />
										<AlertDescription>{errorMessage}</AlertDescription>
									</Alert>
								)}

								<Button
									type="submit"
									className="h-11 w-full bg-[#ffad6a] font-semibold text-[#211107] shadow-[0_10px_30px_rgba(255,141,66,0.2)] hover:bg-[#ffc08e] focus-visible:ring-[#ffad6a]/40"
									disabled={submitting || (mode === 'register' && (!domainId || !areaId))}
								>
									{submitting && <Loader2 className="size-4 animate-spin" />}
									{mode === 'login' ? t('auth.login') : t('auth.createAccount')}
								</Button>
							</FieldGroup>
						</form>
						<p className="mt-5 break-all text-center text-[11px] leading-5 text-white/34">
							{t('auth.connectedTo')} {getBaseUrl()}
						</p>
					</CardContent>
				</Card>
			</main>
		</div>
	);
}
