import { createApp } from "vue";
import App from "./App.vue";
import "./dashboard_style.css";

import i18n from './utils/i18n'
import router from './router'

createApp(App).use(i18n).use(router).mount('#app')