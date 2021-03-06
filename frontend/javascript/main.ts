import '../styles/main.scss'

import 'froide/frontend/javascript/main.ts'

import './misc.ts'
import './donation.ts'
import './betterplace.ts'

if (document.body.dataset.raven) {
  import(/* webpackChunkName: "@sentry/browser" */ '@sentry/browser').then((Sentry) => {
    Sentry.init({
      dsn: document.body.dataset.raven
    })
  })
}
