#! /bin/sh -e

SENDER="e2e-test-$$@example.test"

PAYLOAD="{\"sender\": \"$SENDER\", \"recipients\": \"zxc@asd.qwe\", \"subject\": \"test\", \"body\": \"body\"}"

curl -X POST -H "Content-Type: application/json" -d "$PAYLOAD" http://127.0.0.1:5080/send

FINISH=$((`date +%s` + 5))

while [ `date +%s` -lt $FINISH ]; do
    LOG_ENTRY=`tail -1 smtpstub.log`
    if [ "$LOG_ENTRY" = "$SENDER" ]; then
        exit 0
    fi
    sleep 1
done

exit 1