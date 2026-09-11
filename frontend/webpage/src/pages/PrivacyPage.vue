<script setup>

defineProps({ tr: Function, session: Object });
defineEmits(["navigate", "set-language"]);
</script>

<template>
  <main class="site-container privacy-page">
    <p class="section-kicker">Legal</p>
    <h1>Privacy policy</h1>
    <p class="privacy-updated">Last updated: 14 August 2026</p>
    <p class="privacy-lead">
      The Ultimate Mega Study Tool ("theumst", "we", "us") is responsible for the personal information described in this notice. This notice explains what we collect, why we use it, and the choices available to you.
    </p>

    <section>
      <h2>Information we collect</h2>
      <p>
        When you create or use an account, we collect your username, email address and password in protected form. We also keep a temporary, protected record of email-confirmation and password-recovery links. You may provide a display name, profile description or profile picture. If you use the private beta or study features, we keep your access request, books opened, study position, progress and notes. If you create developer access credentials, we keep their name, status and use history; the full credential is shown only when it is created.
      </p>
      <p>
        For password recovery and service security, we may record the time of a request and its internet address. Our service providers may also create ordinary security records containing an internet address, browser or device type, time, and pages requested. We do not use advertising trackers or behavioural analytics.
      </p>
    </section>

    <section>
      <h2>Why we use it</h2>
      <p>
        We use this information to create and secure accounts, confirm that you can access the email inbox you provide, keep you signed in, restore account access, save your learning activity and notes, review beta access, operate developer features, answer requests, prevent misuse and maintain the service. Email confirmation does not verify your identity or grant access to restricted material. We do so where necessary to provide the service you request, to meet legal obligations, and for our legitimate interests in running a secure and reliable education and research service. We do not make decisions about you that have legal or similarly significant effects using automated processing alone.
      </p>
    </section>

    <section>
      <h2>Who receives it</h2>
      <p>
        We do not sell personal information. Access is limited to authorised members of theumst and service providers that support hosting, secure storage, account-confirmation email and password-recovery email. They may use the information only to provide those services or as required by law. Some providers may handle information outside the United Kingdom; where required, we rely on recognised legal safeguards for those transfers.
      </p>
    </section>

    <section>
      <h2>How long we keep it</h2>
      <p>
        Account information, saved learning activity and notes are kept while your account is active and for as long as reasonably needed to provide the service, resolve disputes or meet legal and security obligations. Sign-in access normally expires after seven days. Email-confirmation links expire after 24 hours and password-recovery links after one hour; both can be used only once. Security records are kept only for as long as reasonably needed for protection, investigation and legal compliance. We delete or remove identifying details when information is no longer needed.
      </p>
    </section>

    <section>
      <h2>Cookies and device storage</h2>
      <p>
        We use one required sign-in cookie so that your account remains available as you move through the service. It is protected from access by page content, is sent only in appropriate requests, and normally lasts seven days. Your language choice is saved on your device. We do not use non-essential advertising or analytics cookies, so there is no optional tracking consent to manage.
      </p>
    </section>

    <section>
      <h2>Your rights</h2>
      <p>
        Depending on the circumstances, you may ask for a copy of your personal information, correct it, delete it, limit or object to its use, or receive information you supplied in a portable form. You may also complain to the UK Information Commissioner's Office at <a href="https://ico.org.uk/make-a-complaint/" rel="noreferrer">ico.org.uk</a>. To ask a question or exercise a right, email <a href="mailto:accounts@theumst.com">accounts@theumst.com</a>. We may need to confirm your identity before acting on a request.
      </p>
    </section>

    <section>
      <h2>Changes</h2>
      <p>
        We will update this notice if the way we use personal information changes materially. The current version will remain available on this page, with its effective date.
      </p>
    </section>
  </main>
</template>
