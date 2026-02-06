"""
Email utilities for sending password reset and notification emails
"""

import logging
from flask import url_for
from flask_mail import Message

logger = logging.getLogger(__name__)


def send_password_reset_email(mail, email, token, clinic_name):
    """
    Send password reset email
    
    Args:
        mail: Flask-Mail instance
        email: Recipient email address
        token: Password reset token
        clinic_name: Name of the clinic/office
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        reset_url = url_for('admin_reset_password_get', token=token, _external=True)
        
        msg = Message(
            subject=f"{clinic_name} - Password Reset Request",
            recipients=[email],
            html=f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: linear-gradient(135deg, #4682B4, #83c9f4); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                            <h1 style="color: white; margin: 0;">Password Reset Request</h1>
                        </div>
                        
                        <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                            <p>Hello,</p>
                            
                            <p>We received a request to reset your admin password for <strong>{clinic_name}</strong>.</p>
                            
                            <p>Click the button below to reset your password:</p>
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{reset_url}" 
                                   style="background: linear-gradient(135deg, #4682B4, #83c9f4); 
                                          color: white; 
                                          padding: 15px 40px; 
                                          text-decoration: none; 
                                          border-radius: 50px; 
                                          display: inline-block;
                                          font-weight: bold;">
                                    Reset Password
                                </a>
                            </div>
                            
                            <p>Or copy and paste this link into your browser:</p>
                            <p style="word-break: break-all; background: white; padding: 10px; border-radius: 5px; font-size: 12px;">
                                {reset_url}
                            </p>
                            
                            <p style="color: #dc3545; font-weight: bold;">This link will expire in 1 hour.</p>
                            
                            <p>If you didn't request this password reset, please ignore this email or contact your system administrator.</p>
                            
                            <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                            
                            <p style="font-size: 12px; color: #666;">
                                This is an automated message from {clinic_name}.<br>
                                Please do not reply to this email.
                            </p>
                        </div>
                    </div>
                </body>
            </html>
            """
        )
        
        mail.send(msg)
        logger.info(f"Password reset email sent to {email}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {str(e)}")
        return False


def send_password_changed_notification(mail, email, clinic_name):
    """
    Send notification email when password is successfully changed
    
    Args:
        mail: Flask-Mail instance
        email: Recipient email address
        clinic_name: Name of the clinic/office
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        msg = Message(
            subject=f"{clinic_name} - Password Changed Successfully",
            recipients=[email],
            html=f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: linear-gradient(135deg, #28a745, #5cb85c); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                            <h1 style="color: white; margin: 0;">✓ Password Changed</h1>
                        </div>
                        
                        <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                            <p>Hello,</p>
                            
                            <p>Your admin password for <strong>{clinic_name}</strong> has been successfully changed.</p>
                            
                            <p>If you made this change, no further action is needed.</p>
                            
                            <p style="color: #dc3545; font-weight: bold;">
                                ⚠️ If you did NOT change your password, please contact your system administrator immediately.
                            </p>
                            
                            <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                            
                            <p style="font-size: 12px; color: #666;">
                                This is an automated message from {clinic_name}.<br>
                                Please do not reply to this email.
                            </p>
                        </div>
                    </div>
                </body>
            </html>
            """
        )
        
        mail.send(msg)
        logger.info(f"Password change notification sent to {email}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send password change notification to {email}: {str(e)}")
        return False


def send_appointment_notification(mail, recipient_email, appointment_data, clinic_info):
    """
    Send appointment request notification to admin
    
    Args:
        mail: Flask-Mail instance
        recipient_email: Admin email address
        appointment_data: Dict with appointment request details
        clinic_info: Dict with clinic information
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        msg = Message(
            subject=f"New Appointment Request - {appointment_data['name']}",
            recipients=[recipient_email],
            html=f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: linear-gradient(135deg, #4682B4, #83c9f4); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                            <h1 style="color: white; margin: 0;">📅 New Appointment Request</h1>
                        </div>
                        
                        <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                            <h2 style="color: #4682B4; margin-top: 0;">Patient Information</h2>
                            
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Name:</td>
                                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">{appointment_data['name']}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Contact:</td>
                                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">{appointment_data['contact']}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Preferred Times:</td>
                                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">{appointment_data['preferred_times']}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Service:</td>
                                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">{appointment_data['service']}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px; font-weight: bold; vertical-align: top;">Note:</td>
                                    <td style="padding: 10px;">{appointment_data.get('note', 'N/A')}</td>
                                </tr>
                            </table>
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{url_for('admin_requests', _external=True)}" 
                                   style="background: linear-gradient(135deg, #4682B4, #83c9f4); 
                                          color: white; 
                                          padding: 15px 40px; 
                                          text-decoration: none; 
                                          border-radius: 50px; 
                                          display: inline-block;
                                          font-weight: bold;">
                                    View in Admin Panel
                                </a>
                            </div>
                            
                            <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                            
                            <p style="font-size: 12px; color: #666;">
                                This is an automated notification from {clinic_info['office_name']}.<br>
                                Please do not reply to this email.
                            </p>
                        </div>
                    </div>
                </body>
            </html>
            """
        )
        
        mail.send(msg)
        logger.info(f"Appointment notification sent to {recipient_email}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send appointment notification: {str(e)}")
        return False