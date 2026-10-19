import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';

import enTranslations from './locales/en.json';
import viTranslations from './locales/vi.json';
import zhTranslations from './locales/zh.json';
import { personalEn, personalVi } from './personal';

i18n.use(LanguageDetector)
	.use(initReactI18next)
	.init({
		resources: {
			en: { translation: { ...enTranslations, personal: personalEn } },
			vi: { translation: { ...viTranslations, personal: personalVi } },
			zh: { translation: { ...zhTranslations, personal: personalEn } },
		},
		fallbackLng: ['vi', 'en'],
		supportedLngs: ['vi', 'en', 'zh'],
		nonExplicitSupportedLngs: true,
		interpolation: {
			escapeValue: false,
		},
		detection: {
			order: ['localStorage'],
			lookupLocalStorage: 'agentscope-ui-language',
			caches: ['localStorage'],
		},
	});

const updateDocumentLanguage = (language: string) => {
	document.documentElement.lang = language.split('-')[0];
};
i18n.on('languageChanged', updateDocumentLanguage);
updateDocumentLanguage(i18n.resolvedLanguage ?? 'vi');

export default i18n;
