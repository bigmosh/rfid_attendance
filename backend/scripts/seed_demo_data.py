"""Seed the two physical cards and one demo device after migrations are applied."""

import logging

from sqlalchemy import select

from app.database import SessionLocal
from app.models import CardStatus, Device, RFIDCard, Student


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger(__name__)


STUDENTS = (
    ("ST001", "Student 1", "77-48-28-61-92"),
    ("ST002", "Student 2", "51-164-2-51-166"),
)
DEVICE = ("attendance-pi-01", "Main Attendance Device")


def seed_demo_data():
    """Create missing demo records without placing them in request handling."""
    with SessionLocal.begin() as session:
        for student_number, name, card_uid in STUDENTS:
            student = session.scalar(
                select(Student).where(Student.student_number == student_number)
            )
            if student is None:
                student = Student(student_number=student_number, name=name)
                session.add(student)
                session.flush()
                LOGGER.info("Created demo student %s", student_number)

            card = session.scalar(select(RFIDCard).where(RFIDCard.uid == card_uid))
            if card is None:
                session.add(
                    RFIDCard(
                        uid=card_uid,
                        student_id=student.id,
                        status=CardStatus.ACTIVE,
                    )
                )
                LOGGER.info("Created demo card for %s", student_number)

        device_id, device_name = DEVICE
        device = session.scalar(select(Device).where(Device.device_id == device_id))
        if device is None:
            session.add(Device(device_id=device_id, name=device_name))
            LOGGER.info("Created demo device %s", device_id)


if __name__ == "__main__":
    seed_demo_data()
