import Alert from 'sentry/components/alert';
import {IconInfo} from 'sentry/icons';
import {t} from 'sentry/locale';

function ComingSoon(): React.ReactElement {
  return (
    <Alert type="info" icon={<IconInfo size="md" />}>
      {t('This feature is coming soon!')}
    </Alert>
  );
}

export default ComingSoon;
